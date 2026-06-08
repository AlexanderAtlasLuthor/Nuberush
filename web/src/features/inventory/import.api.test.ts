// F2.27.8: API-layer unit tests for the Excel import functions.
//
// Same strategy as api.test.ts: stub `@/api` and assert URL, method and
// that the body is the FormData carrying the `file` field. Content-Type
// is intentionally NOT set by these functions (FormData → the browser
// supplies the multipart boundary; apiRequest enforces that).

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import { confirmInventoryImport, previewInventoryImport } from "./api";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

function makeFile() {
  return new File([new Uint8Array([1, 2, 3])], "inv.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

describe("previewInventoryImport", () => {
  it("POSTs FormData with the file field to the preview path", async () => {
    const file = makeFile();
    await previewInventoryImport({ storeId: STORE_ID, file });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/stores/${STORE_ID}/inventory/import/preview`,
    );
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeInstanceOf(FormData);
    expect((options?.body as FormData).get("file")).toBe(file);
    // Must not hand-set Content-Type for multipart uploads.
    expect(options?.headers).toBeUndefined();
  });

  it("omits create_missing when not requested", async () => {
    await previewInventoryImport({ storeId: STORE_ID, file: makeFile() });
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect((options?.body as FormData).get("create_missing")).toBeNull();
  });

  it("appends create_missing=true when requested", async () => {
    await previewInventoryImport({
      storeId: STORE_ID,
      file: makeFile(),
      createMissing: true,
    });
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect((options?.body as FormData).get("create_missing")).toBe("true");
  });
});

describe("confirmInventoryImport", () => {
  it("POSTs FormData with the file field to the confirm path", async () => {
    const file = makeFile();
    await confirmInventoryImport({ storeId: STORE_ID, file });

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/stores/${STORE_ID}/inventory/import/confirm`,
    );
    expect(options?.method).toBe("POST");
    expect((options?.body as FormData).get("file")).toBe(file);
  });

  it("URL-encodes the store id in the path", async () => {
    await confirmInventoryImport({ storeId: "a b/c", file: makeFile() });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores/a%20b%2Fc/inventory/import/confirm");
  });
});
