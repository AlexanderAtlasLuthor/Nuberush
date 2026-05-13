import { LegalDocumentPage } from "./LegalDocumentPage";
import { TERMS_DRAFT } from "../content/legalDrafts";

export function TermsPage() {
  return <LegalDocumentPage document={TERMS_DRAFT} />;
}

export default TermsPage;
