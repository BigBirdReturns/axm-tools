export function ownedCaptureDescriptor({ assetId, capturedAt, position, heading, license = "first-party" }) {
  if (!assetId) {
    return {
      provider: "owned_capture",
      available: false,
      failureReason: "No consented first-party capture is registered.",
    };
  }
  return {
    provider: "owned_capture",
    available: true,
    assetId,
    capturedAt,
    position,
    heading,
    license,
    requiresPrivacyReview: true,
    requiresRegistrationReceipt: true,
  };
}
