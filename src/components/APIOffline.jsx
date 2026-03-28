/**
 * APIOffline — shown when the Aurora API backend is unreachable
 * Displays the endpoint being called and a retry button.
 */
import { AlertTriangle, RefreshCw, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function APIOffline({ error, endpoint, onRetry, hint }) {
  const isNotFound = error?.includes("404") || error?.includes("Not Found");
  const isNetwork  = error?.includes("Failed to fetch") || error?.includes("NetworkError");

  return (
    <Card className="border-amber-300 bg-amber-50 max-w-xl">
      <CardContent className="py-5 px-5 space-y-3">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-sm font-semibold text-amber-900">
              {isNetwork ? "Aurora API unreachable" : isNotFound ? "Endpoint not yet implemented" : "Aurora API error"}
            </p>
            {endpoint && (
              <p className="text-xs font-mono text-amber-800 bg-amber-100 rounded px-2 py-0.5 inline-block">
                {endpoint}
              </p>
            )}
            <p className="text-xs text-amber-700">
              {hint || (isNotFound
                ? "This API route exists in the FastAPI spec but the router is not yet mounted in main.py."
                : isNetwork
                ? "The Aurora API container may be starting up or DNS is not resolving."
                : error)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-1">
          {onRetry && (
            <Button size="sm" variant="outline" className="gap-1.5" onClick={onRetry}>
              <RefreshCw className="w-3 h-3" /> Retry
            </Button>
          )}
          <a
            href="https://api.aurora-osi.com/health/live"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-amber-700 underline flex items-center gap-1"
          >
            Check API health <ExternalLink className="w-3 h-3" />
          </a>
          <a
            href="/api-console"
            className="text-xs text-amber-700 underline"
          >
            Open API Console →
          </a>
        </div>
      </CardContent>
    </Card>
  );
}