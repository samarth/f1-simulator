export default function Header() {
  return (
    <header className="bg-surface-800 border-b border-surface-400 px-6 py-4">
      <h1 className="text-2xl font-display font-bold text-white tracking-wide">
        <span className="text-f1-red">F1</span> Strategy Simulator
      </h1>
      <p className="text-sm text-gray-400 mt-1">
        Play race engineer — plan your pit stops and see how you'd do
      </p>
    </header>
  );
}
