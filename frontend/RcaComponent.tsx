import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./RcaComponent.css";

interface RcaComponentProps {
  build: string;
  backendUrl?: string;
}

export function RcaComponent(
  { build = "", backendUrl = "" }: RcaComponentProps,
) {
  const [status, setStatus] = useState<string[]>([]);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);

  async function getReport() {
    setStatus([]);
    setResult("");
    setError("");

    if (!build) {
      setStatus(
        (_) => ["Build is missing, try adding ?build=... to the page url."]
      );
      return;
    }
    let eventSource;
    if (eventSource) {
      eventSource.close();
    }

    function handleMessage(event, body) {
      switch (event) {
        case "progress":
          setStatus((prevStatus) => [...prevStatus, body]);
          break;
        case "chunk":
          setResult((prevResult) => prevResult + body);
          break;
        case "status":
          console.log("Setting status", body);
          if (body != "completed") {
            setError(body);
          }
          if (eventSource) {
            eventSource.close();
          }
          eventSource = null;
          break;
      }
    }

    try {
      const submitRes = await fetch(
        `${backendUrl}/submit?build=${encodeURIComponent(build)}`,
        {
          method: "PUT",
        },
      );

      const submitData = await submitRes.json();

      if (submitData.status === "COMPLETED") {
        const reportRes = await fetch(
          `${backendUrl}/report?build=${encodeURIComponent(build)}`,
        );
        if (!reportRes.ok) {
          throw new Error("Failed to fetch completed report");
        }
        const reportJson = await reportRes.json();
        reportJson.forEach(([event, body]) => {
          handleMessage(event, body);
        });
        return;
      }

      eventSource = new EventSource(
        `${backendUrl}/watch?build=${encodeURIComponent(build)}`,
      );

      eventSource.onmessage = (e) => {
        const [event, body] = JSON.parse(e.data);
        handleMessage(event, body);
      };

      eventSource.onerror = () => {
        setError(
          "Failed to connect to the server. Please ensure the backend is running and accessible.",
        );
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      };
    } catch (err) {
      console.error("RCA failed", err);
      setError(
        err instanceof Error ? err.message : "An unknown error occurred.",
      );
    }
  }
  useEffect(() => {
    getReport();
    return () => {};
  }, [build]);
  return (
    <div className="bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-white min-h-screen flex flex-col items-center p-4 sm:p-6 lg:p-8 transition-colors duration-300">
      <div className="w-full max-w-4xl">
        <header className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold text-center">RCAv2</h1>
        </header>
        <main className="w-full flex flex-col items-center gap-6">
          {error && (
            <div className="w-full bg-red-50 dark:bg-gray-800 border border-red-500 rounded-md p-4">
              <h2 className="text-xl font-semibold text-red-700 dark:text-red-400 border-b border-red-200 dark:border-gray-700 pb-2 mb-3">
                Error
              </h2>
              <pre className="text-red-600 dark:text-red-300 whitespace-pre-wrap break-words font-mono">{error}</pre>
            </div>
          )}

          {status.length > 0 && (
            <div className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-md p-4">
              <h2 className="text-xl font-semibold border-b border-gray-200 dark:border-gray-700 pb-2 mb-3">
                Analysis Status
              </h2>
              <ul className="list-none p-0 m-0 font-mono text-sm">
                {status.map((msg, index) => (
                  <li key={index} className="pt-1">{msg}</li>
                ))}
              </ul>
            </div>
          )}

          {result && (
            <div className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-md p-4">
              <h2 className="text-xl font-semibold border-b border-gray-200 dark:border-gray-700 pb-2 mb-3">
                Analysis Result
              </h2>
              <div className="prose dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
