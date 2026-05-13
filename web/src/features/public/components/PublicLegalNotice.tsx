// F2.21 contract §9 requires every legal page to render this exact
// notice so visitors understand the documents are operational drafts,
// not counsel-reviewed binding text. The wording is locked by the
// contract — do not edit without updating docs/f2.21-contract-lock.md.

export const LEGAL_DRAFT_NOTICE =
  "Draft notice: This document is provided as an operational draft for review and approval by qualified legal counsel before public launch.";

export function PublicLegalNotice() {
  return (
    <aside
      role="note"
      aria-label="Draft notice"
      className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm text-foreground leading-relaxed"
    >
      <p>
        <strong className="font-semibold">Draft notice:</strong>{" "}
        This document is provided as an operational draft for review and
        approval by qualified legal counsel before public launch.
      </p>
    </aside>
  );
}

export default PublicLegalNotice;
