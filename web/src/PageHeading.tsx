import { ReactNode, useEffect, useRef } from "react";

/** A page's h2. Takes focus when you navigate to the page, so screen readers announce it. */
export function PageHeading({ id, focus, children }: { id: string; focus: boolean; children: ReactNode }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focus) heading.current?.focus();
  }, [focus]);
  return (
    <h2 id={id} ref={heading} tabIndex={-1}>
      {children}
    </h2>
  );
}
