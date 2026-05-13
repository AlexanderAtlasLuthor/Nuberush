import { LegalDocumentPage } from "./LegalDocumentPage";
import { MERCHANT_AGREEMENT_DRAFT } from "../content/legalDrafts";

export function MerchantAgreementPage() {
  return <LegalDocumentPage document={MERCHANT_AGREEMENT_DRAFT} />;
}

export default MerchantAgreementPage;
