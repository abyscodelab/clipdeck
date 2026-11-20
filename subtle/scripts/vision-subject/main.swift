import Foundation
import AVFoundation
import Vision
import CoreImage
import CoreVideo

// vision-subject: where are the faces, the hands and the person at given moments of a video?
// Used by Subtle's caption placement (scripts/placement.py). Apple frameworks only.

func eprint(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }
func fail(_ s: String) -> Never { eprint("vision-subject: error: " + s); exit(1) }
signal(SIGPIPE, SIG_IGN)

let usage = """
usage:
  vision-subject sample <video> --times 0.5,1.2,3 [--bands 24]
  vision-subject sample <video> --times-file <file with one time in seconds per line> [--bands 24]
prints one JSON object: {"frames":[{"t":0.5,"faces":[[x,y,w,h]],"hands":[[x,y,w,h]],"person":[...bands...]}]}
All boxes are fractions of the upright frame with the origin at the top left. `person` has one value per
horizontal band: the share of that band's width covered by the person (0..1).
"""

func f4(_ v: Double) -> String { String(format: "%.4f", max(0, min(1, v))) }

/// Vision boxes have a bottom-left origin; flip to top-left.
func box(_ r: CGRect) -> String {
    "[\(f4(Double(r.minX))),\(f4(1 - Double(r.maxY))),\(f4(Double(r.width))),\(f4(Double(r.height)))]"
}

func handBox(_ o: VNHumanHandPoseObservation) -> CGRect? {
    guard let pts = try? o.recognizedPoints(.all) else { return nil }
    let good = pts.values.filter { $0.confidence > 0.25 }
    guard good.count >= 5 else { return nil }
    let xs = good.map { Double($0.location.x) }, ys = good.map { Double($0.location.y) }
    return CGRect(x: xs.min()!, y: ys.min()!, width: xs.max()! - xs.min()!, height: ys.max()! - ys.min()!)
}

func sample(video: String, times: [Double], bands: Int) async {
    let asset = AVURLAsset(url: URL(fileURLWithPath: video))
    guard let dur = try? await asset.load(.duration), dur.seconds > 0 else { fail("cannot read '\(video)'") }
    let gen = AVAssetImageGenerator(asset: asset)
    gen.appliesPreferredTrackTransform = true
    gen.requestedTimeToleranceBefore = .zero
    gen.requestedTimeToleranceAfter = .zero
    var rows: [String] = []
    for t0 in times {
        let t = min(max(0, t0), max(0, dur.seconds - 0.05))
        let img: CGImage
        do { img = try await gen.image(at: CMTime(seconds: t, preferredTimescale: 600)).image }
        catch { eprint("vision-subject: cannot decode frame at \(t)s"); continue }
        let handler = VNImageRequestHandler(cgImage: img, options: [:])
        let faceReq = VNDetectFaceRectanglesRequest()
        let handReq = VNDetectHumanHandPoseRequest()
        handReq.maximumHandCount = 4
        let segReq = VNGeneratePersonSegmentationRequest()
        segReq.qualityLevel = .balanced
        segReq.outputPixelFormat = kCVPixelFormatType_OneComponent8
        do { try handler.perform([faceReq, handReq, segReq]) } catch { fail("Vision failed: \(error.localizedDescription)") }
        let faces = (faceReq.results ?? []).map { box($0.boundingBox) }
        let hands = (handReq.results ?? []).compactMap { handBox($0) }.map { box($0) }
        var person = [Double](repeating: 0, count: bands)
        if let obs = segReq.results?.first as? VNPixelBufferObservation {
            let pb = obs.pixelBuffer
            CVPixelBufferLockBaseAddress(pb, .readOnly)
            if let base = CVPixelBufferGetBaseAddress(pb) {
                let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb), rb = CVPixelBufferGetBytesPerRow(pb)
                let p = base.assumingMemoryBound(to: UInt8.self)
                var sum = [Double](repeating: 0, count: bands), cnt = [Double](repeating: 0, count: bands)
                for y in 0..<h {
                    var above = 0
                    let r = p + y * rb
                    for x in 0..<w where r[x] >= 128 { above += 1 }
                    let b = min(bands - 1, y * bands / h)
                    sum[b] += Double(above) / Double(w); cnt[b] += 1
                }
                for b in 0..<bands where cnt[b] > 0 { person[b] = sum[b] / cnt[b] }
            }
            CVPixelBufferUnlockBaseAddress(pb, .readOnly)
        }
        rows.append("{\"t\":\(String(format: "%.3f", t0)),\"faces\":[\(faces.joined(separator: ","))],\"hands\":[\(hands.joined(separator: ","))],\"person\":[\(person.map(f4).joined(separator: ","))]}")
    }
    print("{\"bands\":\(bands),\"frames\":[\(rows.joined(separator: ","))]}")
}

var args = Array(CommandLine.arguments.dropFirst())
guard args.count >= 2, args[0] == "sample" else { eprint(usage); exit(2) }
let video = args[1]
var times: [Double] = []
var bands = 24
var i = 2
while i < args.count {
    switch args[i] {
    case "--times": i += 1; times += (args[safe: i] ?? "").split(separator: ",").compactMap { Double($0) }
    case "--times-file":
        i += 1
        guard let txt = try? String(contentsOfFile: args[safe: i] ?? "", encoding: .utf8) else { fail("cannot read times file") }
        let seps = CharacterSet(charactersIn: "\n, ")
        for part in txt.components(separatedBy: seps) { if let v = Double(part) { times.append(v) } }
    case "--bands": i += 1; bands = max(4, Int(args[safe: i] ?? "") ?? 24)
    default: fail("unknown option \(args[i])\n" + usage)
    }
    i += 1
}
extension Array { subscript(safe i: Int) -> Element? { indices.contains(i) ? self[i] : nil } }
if times.isEmpty { fail("no times given\n" + usage) }
await sample(video: video, times: times, bands: bands)
