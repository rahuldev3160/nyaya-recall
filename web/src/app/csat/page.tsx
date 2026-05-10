export default function CsatPage() {
  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-bold">CSAT Practice</h1>
      <div className="bg-gray-900 border border-amber-900 rounded-xl p-6">
        <p className="text-amber-400 font-medium mb-2">CSAT module — coming soon</p>
        <p className="text-gray-400 text-sm">
          Add your CSAT study material to the CSAT folder inside your UPSC directory and
          re-run the ingestion script. Once content is indexed, this page will activate with
          comprehension, reasoning, and numeracy practice sessions.
        </p>
      </div>
    </div>
  );
}
