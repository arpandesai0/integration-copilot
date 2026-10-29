import { PublicGuide } from "@/components/public-guide";
export default async function Page({
  params,
}: {
  params: Promise<{ shareSlug: string }>;
}) {
  const { shareSlug } = await params;
  return <PublicGuide slug={shareSlug} />;
}
