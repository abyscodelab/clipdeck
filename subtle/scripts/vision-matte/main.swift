import Foundation
import AVFoundation
import Vision
import CoreImage
import CoreVideo
import Accelerate

// MARK: - helpers

func eprint(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }
func fail(_ s: String) -> Never { eprint("vision-matte: error: " + s); exit(1) }
signal(SIGPIPE, SIG_IGN)

let usage = """
usage:
  vision-matte check <video> [--samples 12] [--band-height 0.14]
  vision-matte matte <video> --out <matte.mp4> [--quality accurate|balanced|fast] [--no-ema]
"""

/// Mask-motion threshold (mean abs difference between consecutive RAW masks, 0..1) above which
/// the temporal EMA is skipped for that frame. See README for how it was picked.
let emaMotionThreshold = 0.012
/// `check`: mean mask difference between consecutive samples (seconds apart) above which we skip.
let checkMotionThreshold = 0.20

func qualityLevel(_ s: String) -> VNGeneratePersonSegmentationRequest.QualityLevel {
    switch s {
    case "accurate": return .accurate
    case "balanced": return .balanced
    case "fast": return .fast
    default: fail("unknown --quality '\(s)' (accurate|balanced|fast)")
    }
}

func makeRequest(_ q: String) -> VNGeneratePersonSegmentationRequest {
    let r = VNGeneratePersonSegmentationRequest()
    r.qualityLevel = qualityLevel(q)
    r.outputPixelFormat = kCVPixelFormatType_OneComponent8
    return r
}

func f3(_ v: Double) -> String { String(format: "%.4f", v) }

/// Run a request on a pixel buffer or CGImage and hand the 8-bit mask to `body`.
func withMask(_ req: VNGeneratePersonSegmentationRequest, _ handler: VNImageRequestHandler,
              _ body: (UnsafePointer<UInt8>, Int, Int, Int) -> Void) {
    do { try handler.perform([req]) } catch { fail("Vision failed: \(error.localizedDescription)") }
    guard let obs = req.results?.first as? VNPixelBufferObservation else { fail("Vision returned no mask") }
    let pb = obs.pixelBuffer
    CVPixelBufferLockBaseAddress(pb, .readOnly)
    defer { CVPixelBufferUnlockBaseAddress(pb, .readOnly) }
    guard let base = CVPixelBufferGetBaseAddress(pb) else { fail("mask has no pixels") }
    body(base.assumingMemoryBound(to: UInt8.self), CVPixelBufferGetWidth(pb), CVPixelBufferGetHeight(pb),
         CVPixelBufferGetBytesPerRow(pb))
}

final class Plane {
    let w: Int, h: Int, p: UnsafeMutablePointer<UInt8>
    init(_ w: Int, _ h: Int) {
        self.w = w; self.h = h
        p = .allocate(capacity: w * h); p.initialize(repeating: 0, count: w * h)
    }
    deinit { p.deallocate() }
    var vb: vImage_Buffer {
        vImage_Buffer(data: p, height: vImagePixelCount(h), width: vImagePixelCount(w), rowBytes: w)
    }
}

// MARK: - cleanup (hole fill + small blob removal on a coarse grid)

final class Cleaner {
    let W: Int, H: Int, cs = 4, cw: Int, ch: Int
    var fg: [UInt8], lab: [Int32], act: [UInt8], stack: [Int32]
    init(_ W: Int, _ H: Int) {
        self.W = W; self.H = H
        cw = (W + 3) / 4; ch = (H + 3) / 4
        fg = [UInt8](repeating: 0, count: cw * ch)
        lab = [Int32](repeating: 0, count: cw * ch)
        act = [UInt8](repeating: 0, count: cw * ch)
        stack = []; stack.reserveCapacity(cw * ch)
    }

    /// Removes foreground blobs under `minBlob` (fraction of frame) and fills background holes
    /// (not touching the border) under `maxHole`. Works in place on `f`.
    func run(_ f: Plane, minBlob: Double, maxHole: Double) {
        let n = cw * ch
        for cy in 0..<ch {
            let y0 = cy * cs, y1 = min(H, y0 + cs)
            for cx in 0..<cw {
                let x0 = cx * cs, x1 = min(W, x0 + cs)
                var s = 0
                for y in y0..<y1 { let r = f.p + y * W; for x in x0..<x1 { s += Int(r[x]) } }
                fg[cy * cw + cx] = s >= 128 * (y1 - y0) * (x1 - x0) ? 1 : 0
            }
        }
        for i in 0..<n { lab[i] = 0; act[i] = 0 }
        let minBlobCells = Int(minBlob * Double(n)), maxHoleCells = Int(maxHole * Double(n))

        // foreground components (8-connected); small ones get action 1 (remove)
        var next: Int32 = 1
        var small = [Bool](repeating: false, count: 1)
        for s in 0..<n where fg[s] == 1 && lab[s] == 0 {
            let size = flood(s, target: 1, label: next, eight: true).size
            small.append(size < minBlobCells); next += 1
        }
        for i in 0..<n where fg[i] == 1 && small[Int(lab[i])] { act[i] = 1 }
        // grow removal by one cell into background so the soft rim goes too
        let snapshot = act
        for cy in 0..<ch { for cx in 0..<cw where snapshot[cy * cw + cx] == 1 {
            for dy in -1...1 { for dx in -1...1 {
                let y = cy + dy, x = cx + dx
                if y >= 0 && y < ch && x >= 0 && x < cw && fg[y * cw + x] == 0 { act[y * cw + x] = 1 }
            } }
        } }
        // background holes (4-connected, not touching the border)
        var lab2 = [Int32](repeating: 0, count: n)
        swap(&lab, &lab2)
        var bnext: Int32 = 1
        for s in 0..<n where fg[s] == 0 && lab[s] == 0 {
            let r = flood(s, target: 0, label: bnext, eight: false)
            if !r.border && r.size <= maxHoleCells {
                for i in 0..<n where lab[i] == bnext { act[i] = 2 }
            }
            bnext += 1
        }
        for cy in 0..<ch { for cx in 0..<cw {
            let a = act[cy * cw + cx]
            if a == 0 { continue }
            let v: UInt8 = a == 1 ? 0 : 255
            for y in (cy * cs)..<min(H, cy * cs + cs) {
                (f.p + y * W + cx * cs).update(repeating: v, count: min(W, cx * cs + cs) - cx * cs)
            }
        } }
    }

    func flood(_ start: Int, target: UInt8, label: Int32, eight: Bool) -> (size: Int, border: Bool) {
        stack.removeAll(keepingCapacity: true)
        stack.append(Int32(start)); lab[start] = label
        var size = 0, border = false
        while let c32 = stack.popLast() {
            let c = Int(c32); size += 1
            let cy = c / cw, cx = c % cw
            if cy == 0 || cx == 0 || cy == ch - 1 || cx == cw - 1 { border = true }
            for dy in -1...1 { for dx in -1...1 {
                if (dx == 0 && dy == 0) || (!eight && dx != 0 && dy != 0) { continue }
                let y = cy + dy, x = cx + dx
                if y < 0 || y >= ch || x < 0 || x >= cw { continue }
                let i = y * cw + x
                if fg[i] == target && lab[i] == 0 { lab[i] = label; stack.append(Int32(i)) }
            } }
        }
        return (size, border)
    }
}

// MARK: - orientation

func orientation(for t: CGAffineTransform) -> CGImagePropertyOrientation {
    let a = Int(t.a.rounded()), b = Int(t.b.rounded()), c = Int(t.c.rounded()), d = Int(t.d.rounded())
    switch (a, b, c, d) {
    case (1, 0, 0, 1): return .up
    case (0, 1, -1, 0): return .right
    case (-1, 0, 0, -1): return .down
    case (0, -1, 1, 0): return .left
    case (-1, 0, 0, 1): return .upMirrored
    case (1, 0, 0, -1): return .downMirrored
    case (0, 1, 1, 0): return .rightMirrored
    case (0, -1, -1, 0): return .leftMirrored
    default: return .up
    }
}

func findExecutable(_ name: String) -> String? {
    for dir in (ProcessInfo.processInfo.environment["PATH"] ?? "").split(separator: ":") {
        let p = String(dir) + "/" + name
        if FileManager.default.isExecutableFile(atPath: p) { return p }
    }
    return nil
}

// MARK: - check

func runCheck(video: String, samples: Int, bandHeight: Double) async {
    let asset = AVURLAsset(url: URL(fileURLWithPath: video))
    guard let dur = try? await asset.load(.duration), dur.seconds > 0 else { fail("cannot read '\(video)'") }
    let gen = AVAssetImageGenerator(asset: asset)
    gen.appliesPreferredTrackTransform = true
    gen.requestedTimeToleranceBefore = .zero
    gen.requestedTimeToleranceAfter = .zero
    let req = makeRequest("balanced")

    var masks: [[UInt8]] = []
    var areas: [Double] = [], widths: [Double] = [], softs: [Double] = []
    var personFrames = 0
    var mw = 0, mh = 0
    var rowCover: [Double] = []   // per mask row: mean share of the row covered by the person, over all samples
    for i in 0..<samples {
        let t = CMTime(seconds: dur.seconds * (Double(i) + 0.5) / Double(samples), preferredTimescale: 600)
        let img: CGImage
        do { img = try await gen.image(at: t).image } catch { fail("cannot decode frame at \(t.seconds)s: \(error.localizedDescription)") }
        withMask(req, VNImageRequestHandler(cgImage: img, options: [:])) { p, w, h, rb in
            mw = w; mh = h
            var m = [UInt8](repeating: 0, count: w * h)
            var above = 0, soft = 0
            var colCount = [Int](repeating: 0, count: w)
            if rowCover.count != h { rowCover = [Double](repeating: 0, count: h) }
            for y in 0..<h {
                let r = p + y * rb
                var rowAbove = 0
                for x in 0..<w {
                    let v = r[x]; m[y * w + x] = v
                    if v >= 128 { above += 1; colCount[x] += 1; rowAbove += 1 }
                    if v > 25 && v < 230 { soft += 1 }
                }
                rowCover[y] += Double(rowAbove) / Double(w)
            }
            let n = Double(w * h)
            let area = Double(above) / n
            areas.append(area); softs.append(Double(soft) / n)
            // width of bounding box, counting only columns holding >=0.5% of frame height (ignores specks)
            let minCol = max(1, h / 200)
            let cols = colCount.enumerated().filter { $0.element >= minCol }.map { $0.offset }
            if area >= 0.04 {
                personFrames += 1
                if let lo = cols.first, let hi = cols.last { widths.append(Double(hi - lo + 1) / Double(w)) }
            }
            masks.append(m)
        }
    }
    var motionSum = 0.0
    if masks.count > 1 {
        for i in 1..<masks.count {
            var s = 0
            for j in 0..<(mw * mh) { s += abs(Int(masks[i][j]) - Int(masks[i - 1][j])) }
            motionSum += Double(s) / Double(mw * mh) / 255.0
        }
        motionSum /= Double(masks.count - 1)
    }
    let mean = { (a: [Double]) in a.isEmpty ? 0 : a.reduce(0, +) / Double(a.count) }
    let meanArea = mean(areas), meanWidth = mean(widths), softFraction = mean(softs)
    // Where should the big word sit? Slide a band (the word's height) down the frame and take the place where the
    // person covers about 30% of it: enough to read as "behind", not so much that the word is hidden.
    var bestY = 0.40, bestCover = 0.0, bestScore = Double.infinity
    if !rowCover.isEmpty {
        let h = rowCover.count
        var c = 0.20
        while c <= 0.6201 {
            let y0 = max(0, Int((c - bandHeight / 2) * Double(h))), y1 = min(h, Int((c + bandHeight / 2) * Double(h)))
            if y1 > y0 {
                let cover = rowCover[y0..<y1].reduce(0, +) / Double(y1 - y0) / Double(max(1, samples))
                let score = abs(cover - 0.30) + abs(c - 0.36) * 0.15   // aim for the head, where both sides of the word stay clear
                if score < bestScore { bestScore = score; bestY = c; bestCover = cover }
            }
            c += 0.02
        }
    }
    var rec = "behind"
    var reason = "person in \(personFrames) of \(samples) samples"
    if Double(personFrames) < 0.6 * Double(samples) {
        rec = "skip"; reason = "person found in only \(personFrames) of \(samples) samples (needs at least 60%)"
    } else if motionSum > checkMotionThreshold {
        rec = "skip"; reason = "mask moves a lot between samples (motion \(f3(motionSum)) > \(checkMotionThreshold))"
    } else if bestCover > 0.50 {
        rec = "skip"; reason = "the person covers \(Int(bestCover * 100))% of the frame where a big word could sit (limit 50%), so the words would be hidden"
    } else if bestCover < 0.08 {
        rec = "skip"; reason = "the person never overlaps the area where a big word could sit, so nothing would be behind them"
    } else if softFraction > 0.08 {
        rec = "skip"; reason = "edges are too soft or noisy (\(Int(softFraction * 100))% of pixels are semi-transparent, limit 8%)"
    }
    print("{\"samples\": \(samples), \"personFrames\": \(personFrames), \"meanArea\": \(f3(meanArea)), \"meanWidth\": \(f3(meanWidth)), \"motion\": \(f3(motionSum)), \"softFraction\": \(f3(softFraction)), \"bigY\": \(f3(bestY)), \"bandCoverage\": \(f3(bestCover)), \"recommend\": \"\(rec)\", \"reason\": \"\(reason)\"}")
}

// MARK: - matte

func runMatte(video: String, out: String, quality: String, useEMA: Bool) async {
    guard let ffmpegPath = findExecutable("ffmpeg") else {
        fail("ffmpeg not found on PATH. Install it (for example: brew install ffmpeg) and try again.")
    }
    let asset = AVURLAsset(url: URL(fileURLWithPath: video))
    guard let track = try? await asset.loadTracks(withMediaType: .video).first else { fail("no video track in '\(video)'") }
    guard let xform = try? await track.load(.preferredTransform),
          let minDur = try? await track.load(.minFrameDuration) else { fail("cannot read track info") }
    let nominal = (try? await track.load(.nominalFrameRate)) ?? 0
    var fpsNum = Int(minDur.timescale), fpsDen = Int(minDur.value)
    if minDur.value <= 0 || !minDur.isNumeric { fpsNum = Int((nominal * 1000).rounded()); fpsDen = 1000 }
    if fpsNum <= 0 || fpsDen <= 0 { fail("cannot determine frame rate") }
    let fps = Double(fpsNum) / Double(fpsDen)

    guard let reader = try? AVAssetReader(asset: asset) else { fail("cannot open reader") }
    let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
        kCVPixelBufferIOSurfacePropertiesKey as String: [:],
    ])
    output.alwaysCopiesSampleData = false
    reader.add(output)
    guard reader.startReading() else { fail("cannot start reading: \(reader.error?.localizedDescription ?? "?")") }

    let orient = orientation(for: xform)
    let rotated = [.left, .right, .leftMirrored, .rightMirrored].contains(orient)
    let needsCI = orient != .up
    let ciContext = CIContext(options: [.cacheIntermediates: false])
    var upright: CVPixelBuffer?

    let req = makeRequest(quality)
    let ema = useEMA
    var W = 0, H = 0
    var A: Plane!, B: Plane!, C: Plane!, P: Plane!, E: Plane!, F: Plane!
    var minTemp: UnsafeMutableRawPointer?
    var cleaner: Cleaner!
    var lut = [UInt8](repeating: 0, count: 256)
    for i in 0..<256 {
        let t = min(1, max(0, (Double(i) / 255 - 0.35) / 0.30))
        lut[i] = UInt8((t * t * (3 - 2 * t) * 255).rounded())
    }
    var proc: Process?
    var pipeFD: Int32 = -1
    var frames = 0, emaSkipped = 0
    let t0 = Date()

    while true {
        var finished = false
        autoreleasepool {
            guard let sb = output.copyNextSampleBuffer() else { finished = true; return }
            guard let srcPB = CMSampleBufferGetImageBuffer(sb) else { return }
            var pb = srcPB
            if needsCI {
                let sw = CVPixelBufferGetWidth(srcPB), sh = CVPixelBufferGetHeight(srcPB)
                let ow = rotated ? sh : sw, oh = rotated ? sw : sh
                if upright == nil {
                    CVPixelBufferCreate(nil, ow, oh, kCVPixelFormatType_32BGRA,
                                        [kCVPixelBufferIOSurfacePropertiesKey as String: [:]] as CFDictionary, &upright)
                }
                guard let up = upright else { fail("cannot allocate buffer") }
                let ci = CIImage(cvPixelBuffer: srcPB).oriented(orient)
                ciContext.render(ci, to: up)
                pb = up
            }
            if W == 0 {
                W = CVPixelBufferGetWidth(pb); H = CVPixelBufferGetHeight(pb)
                A = Plane(W, H); B = Plane(W, H); C = Plane(W, H); P = Plane(W, H); E = Plane(W, H); F = Plane(W, H)
                cleaner = Cleaner(W, H)
                var s = A.vb, d = F.vb
                let sz = vImageMin_Planar8(&s, &d, nil, 0, 0, 3, 3, vImage_Flags(kvImageGetTempBufferSize | kvImageEdgeExtend))
                minTemp = UnsafeMutableRawPointer.allocate(byteCount: max(sz, 1), alignment: 64)
                let p = Process()
                p.executableURL = URL(fileURLWithPath: ffmpegPath)
                p.arguments = ["-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "\(W)x\(H)",
                               "-r", "\(fpsNum)/\(fpsDen)", "-i", "-",
                               "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                               "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                               "-movflags", "+faststart", out]
                let pipe = Pipe(); p.standardInput = pipe
                do { try p.run() } catch { fail("cannot start ffmpeg: \(error.localizedDescription)") }
                proc = p; pipeFD = pipe.fileHandleForWriting.fileDescriptor
                keepAlive = pipe
            }
            if CVPixelBufferGetWidth(pb) != W || CVPixelBufferGetHeight(pb) != H { fail("frame size changed mid-stream") }

            // 1. segmentation, scale to display size
            withMask(req, VNImageRequestHandler(cvPixelBuffer: pb, options: [:])) { mp, mw, mh, rb in
                var src = vImage_Buffer(data: UnsafeMutableRawPointer(mutating: mp), height: vImagePixelCount(mh),
                                        width: vImagePixelCount(mw), rowBytes: rb)
                var dst = A.vb
                if mw == W && mh == H && rb == W { memcpy(A.p, mp, W * H) }
                else { _ = vImageScale_Planar8(&src, &dst, nil, vImage_Flags(kvImageNoFlags)) }
            }
            // 1b. blur (3x3 tent, about 1 px) then smoothstep ramp
            var sA = A.vb, dB = B.vb
            _ = vImageTentConvolve_Planar8(&sA, &dB, nil, 0, 0, 3, 3, 0, vImage_Flags(kvImageEdgeExtend))
            var sB = B.vb, dC = C.vb
            lut.withUnsafeBufferPointer { _ = vImageTableLookUp_Planar8(&sB, &dC, $0.baseAddress!, vImage_Flags(kvImageNoFlags)) }
            // 2. temporal EMA, skipped on fast motion
            let n = W * H
            var skip = !ema || frames == 0
            if ema && frames > 0 {
                var sum = 0
                let c = C.p, pp = P.p
                for i in 0..<n { sum += abs(Int(c[i]) - Int(pp[i])) }
                if Double(sum) / Double(n) / 255.0 > emaMotionThreshold { skip = true; emaSkipped += 1 }
            }
            let c = C.p, e = E.p
            if skip { memcpy(e, c, n) }
            else { for i in 0..<n { e[i] = UInt8((3 * Int(c[i]) + 2 * Int(e[i]) + 2) / 5) } }
            swap(&C, &P)
            // 3. erode 1 px
            var sE = E.vb, dF = F.vb
            _ = vImageMin_Planar8(&sE, &dF, minTemp, 0, 0, 3, 3, vImage_Flags(kvImageEdgeExtend))
            // 4. holes + small blobs
            cleaner.run(F, minBlob: 0.02, maxHole: 0.01)

            // write
            var off = 0
            while off < n {
                let w = write(pipeFD, F.p + off, n - off)
                if w <= 0 { fail("ffmpeg closed its input early (is the output path writable?)") }
                off += w
            }
            frames += 1
            if frames % 24 == 0 { eprint("  \(frames) frames, \(Int(Date().timeIntervalSince(t0) * 1000 / Double(frames))) ms/frame") }
        }
        if finished { break }
    }
    if reader.status == .failed { fail("read failed: \(reader.error?.localizedDescription ?? "?")") }
    guard let p = proc, frames > 0 else { fail("no frames decoded") }
    keepAlive?.fileHandleForWriting.closeFile()
    p.waitUntilExit()
    if p.terminationStatus != 0 { fail("ffmpeg exited with status \(p.terminationStatus)") }
    let ms = Date().timeIntervalSince(t0) * 1000 / Double(frames)
    print("{\"frames\": \(frames), \"msPerFrame\": \(String(format: "%.1f", ms)), \"quality\": \"\(quality)\", \"width\": \(W), \"height\": \(H), \"fps\": \(String(format: "%.3f", fps)), \"emaSkippedFrames\": \(emaSkipped)}")
}
var keepAlive: Pipe?

// MARK: - main

var args = Array(CommandLine.arguments.dropFirst())
guard let cmd = args.first, args.count >= 2 else { eprint(usage); exit(2) }
let videoPath = args[1]
func opt(_ name: String) -> String? {
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    return args[i + 1]
}
guard FileManager.default.fileExists(atPath: videoPath) else { fail("no such file: \(videoPath)") }
switch cmd {
case "check":
    await runCheck(video: videoPath, samples: max(2, Int(opt("--samples") ?? "12") ?? 12), bandHeight: Double(opt("--band-height") ?? "0.14") ?? 0.14)
case "matte":
    guard let out = opt("--out") else { eprint(usage); exit(2) }
    await runMatte(video: videoPath, out: out, quality: opt("--quality") ?? "accurate", useEMA: !args.contains("--no-ema"))
default:
    eprint(usage); exit(2)
}
