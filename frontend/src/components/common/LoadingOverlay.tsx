interface Props {
  message?: string;
}

export default function LoadingOverlay({ message = 'Loading...' }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="w-10 h-10 border-4 border-surface-400 border-t-f1-red rounded-full animate-spin" />
      <p className="text-gray-400 font-body text-sm">{message}</p>
    </div>
  );
}
