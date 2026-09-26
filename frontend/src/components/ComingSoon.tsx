import { Card, CardContent } from "@/components/ui/card";

export function ComingSoon({ title, description }: { title: string; description: string }) {
  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <Card className="mt-6">
        <CardContent className="py-12 text-center text-muted-foreground">{description}</CardContent>
      </Card>
    </section>
  );
}
