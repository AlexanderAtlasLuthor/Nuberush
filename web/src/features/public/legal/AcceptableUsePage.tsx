import { LegalDocumentPage } from "./LegalDocumentPage";
import { ACCEPTABLE_USE_DRAFT } from "../content/legalDrafts";

export function AcceptableUsePage() {
  return <LegalDocumentPage document={ACCEPTABLE_USE_DRAFT} />;
}

export default AcceptableUsePage;
