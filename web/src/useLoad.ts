import { useEffect, useState } from "react";
import { ApiError } from "./api";

export type Load<T> = { kind: "loading" } | { kind: "error"; status: number; message: string } | { kind: "done"; data: T };

/** Fetch on mount and whenever key changes. Late answers for an old key are dropped. */
export function useLoad<T>(key: string, load: () => Promise<T>): Load<T> {
  const [state, setState] = useState<Load<T>>({ kind: "loading" });

  useEffect(() => {
    let current = true;
    setState({ kind: "loading" });
    load().then(
      (data) => current && setState({ kind: "done", data }),
      (err: unknown) =>
        current &&
        setState(
          err instanceof ApiError
            ? { kind: "error", status: err.status, message: err.message }
            : { kind: "error", status: 0, message: "Something went wrong. Try again." },
        ),
    );
    return () => {
      current = false;
    };
    // load is a fresh closure every render; key says when it really changed
  }, [key]);

  return state;
}
