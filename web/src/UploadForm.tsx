import { FormEvent, useRef, useState } from "react";
import { SHELF_CODE, validateFile } from "./api";

interface Props {
  busy: boolean;
  onScan: (file: File, shelf: string) => void;
}

export function UploadForm({ busy, onScan }: Props) {
  const [fileError, setFileError] = useState<string | null>(null);
  const [shelfError, setShelfError] = useState<string | null>(null);
  const photoInput = useRef<HTMLInputElement>(null);
  const shelfInput = useRef<HTMLInputElement>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const photo = photoInput.current?.files?.[0];
    const shelf = shelfInput.current?.value.trim() ?? "";

    const fileProblem = validateFile(photo);
    const shelfProblem = shelf && !SHELF_CODE.test(shelf) ? "Use letters, numbers, dots, dashes, or underscores." : null;
    setFileError(fileProblem);
    setShelfError(shelfProblem);

    if (fileProblem) {
      photoInput.current?.focus();
    } else if (shelfProblem) {
      shelfInput.current?.focus();
    } else if (photo) {
      onScan(photo, shelf);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate aria-labelledby="upload-heading">
      <h2 id="upload-heading">Scan a shelf</h2>

      <div className="field">
        <label htmlFor="photo">Shelf photo</label>
        <p id="photo-hint" className="hint">
          JPEG, PNG, or WebP, up to 10 MB. Face the shelf straight on.
        </p>
        <input
          ref={photoInput}
          id="photo"
          name="photo"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={() => setFileError(null)}
          aria-describedby={fileError ? "photo-hint photo-error" : "photo-hint"}
          aria-invalid={fileError ? true : undefined}
        />
        {fileError && (
          <p id="photo-error" className="error">
            {fileError}
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="shelf">Shelf code (optional)</label>
        <p id="shelf-hint" className="hint">
          Used to track this shelf over time, like aisle4-bay2.
        </p>
        <input
          ref={shelfInput}
          id="shelf"
          name="shelf"
          type="text"
          autoComplete="off"
          spellCheck={false}
          onChange={() => setShelfError(null)}
          aria-describedby={shelfError ? "shelf-hint shelf-error" : "shelf-hint"}
          aria-invalid={shelfError ? true : undefined}
        />
        {shelfError && (
          <p id="shelf-error" className="error">
            {shelfError}
          </p>
        )}
      </div>

      <button type="submit" disabled={busy} aria-disabled={busy}>
        {busy ? "Scanning…" : "Scan shelf"}
      </button>
    </form>
  );
}
