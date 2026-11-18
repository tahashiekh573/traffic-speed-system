import { useCallback, useEffect, useRef, useState } from "react";
import { trafficApi } from "../api/trafficApi";
import { POLL_INTERVAL_MS } from "../config";

const MAX_POLL_FAILURES = 5;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Owns the upload -> background job -> polling lifecycle.
 * Returns state plus actions the UI and the robot assistant can call.
 */
export function useVideoAnalysis(config, { onComplete } = {}) {
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [processedVideoUrl, setProcessedVideoUrl] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const activeRun = useRef(0);

  // Revoke the local preview URL whenever it changes or the app unmounts.
  useEffect(() => {
    return () => {
      if (videoUrl) URL.revokeObjectURL(videoUrl);
    };
  }, [videoUrl]);

  // Stop polling when the component unmounts.
  useEffect(() => () => {
    activeRun.current += 1;
  }, []);

  const resetOutput = () => {
    setProcessedVideoUrl("");
    setPreviewUrl("");
    setResult(null);
    setProgress(null);
    setError("");
  };

  const selectFile = useCallback(
    (file) => {
      if (!file) return false;

      const allowed = String(config.allowed_video_extensions)
        .split(",")
        .map((ext) => ext.trim().replace(".", "").toLowerCase())
        .filter(Boolean);
      const extension = file.name.split(".").pop().toLowerCase();

      if (!allowed.includes(extension)) {
        setError(`Please select a ${allowed.join(" / ").toUpperCase()} video.`);
        return false;
      }

      if (file.size > config.max_upload_size_mb * 1024 * 1024) {
        setError(`Video size must be less than ${config.max_upload_size_mb} MB.`);
        return false;
      }

      setVideoFile(file);
      setVideoUrl(URL.createObjectURL(file));
      resetOutput();
      return true;
    },
    [config.allowed_video_extensions, config.max_upload_size_mb]
  );

  const removeVideo = useCallback(() => {
    activeRun.current += 1;
    setVideoFile(null);
    setVideoUrl("");
    setIsProcessing(false);
    resetOutput();
  }, []);

  const analyze = useCallback(async () => {
    if (!videoFile || isProcessing) return;

    const runId = ++activeRun.current;
    const isCurrent = () => runId === activeRun.current;

    setIsProcessing(true);
    resetOutput();
    setProgress({
      status: "uploading",
      upload_percent: 0,
      processed_frames: 0,
      total_frames: 0,
      progress_percent: 0,
    });

    try {
      const job = await trafficApi.uploadVideo(videoFile, (percent) => {
        if (isCurrent()) {
          setProgress((current) => ({ ...current, upload_percent: percent }));
        }
      });
      if (!job.processing_id) throw new Error("Backend did not return a processing ID.");
      if (!isCurrent()) return;
      setProgress(job);

      let failures = 0;

      while (isCurrent()) {
        await sleep(POLL_INTERVAL_MS);
        if (!isCurrent()) return;

        let status;
        try {
          status = await trafficApi.jobStatus(job.processing_id);
          failures = 0;
        } catch (pollError) {
          // A 404 means the backend restarted and lost the job.
          if (pollError.status === 404 || ++failures >= MAX_POLL_FAILURES) {
            throw pollError;
          }
          continue;
        }

        setProgress(status);

        if (status.live?.preview_available) {
          setPreviewUrl(trafficApi.previewUrl(job.processing_id, Date.now()));
        }

        if (status.status === "completed") {
          if (!status.result) throw new Error("Processing completed but no result was returned.");
          setResult(status.result);
          onComplete?.(status.result);
          setProcessedVideoUrl(
            status.result.output_video_url
              ? trafficApi.outputUrl(status.result.output_video_url)
              : ""
          );
          return;
        }

        if (status.status === "failed") {
          throw new Error(status.error || "Video processing failed.");
        }
      }
    } catch (err) {
      if (isCurrent()) setError(err.message || "Video processing failed.");
    } finally {
      if (isCurrent()) setIsProcessing(false);
    }
  }, [videoFile, isProcessing, onComplete]);

  return {
    videoFile,
    videoUrl,
    processedVideoUrl,
    previewUrl,
    isProcessing,
    progress,
    result,
    error,
    selectFile,
    removeVideo,
    analyze,
    setError,
  };
}
