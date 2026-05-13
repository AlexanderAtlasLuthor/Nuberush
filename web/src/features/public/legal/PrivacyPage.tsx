import { LegalDocumentPage } from "./LegalDocumentPage";
import { PRIVACY_DRAFT } from "../content/legalDrafts";

export function PrivacyPage() {
  return <LegalDocumentPage document={PRIVACY_DRAFT} />;
}

export default PrivacyPage;
