export default function ModuleSelector({ selected, onChange }) {
  const modules = [
    { id: 'home', label: 'Home' },
    { id: 'school', label: 'School' },
    { id: 'office', label: 'Office' },
  ];

  return (
    <div className="inline-flex rounded-lg border bg-white shadow-sm overflow-hidden">
      {modules.map((m) => {
        const isActive = selected === m.id;
        return (
          <button
            key={m.id}
            type="button"
            onClick={() => onChange(m.id)}
            className={[
              'px-4 py-2 text-sm font-medium',
              isActive ? 'bg-blue-600 text-white' : 'bg-white text-gray-700',
              'hover:bg-blue-50',
              'border-r last:border-r-0',
            ].join(' ')}
          >
            {m.label}
          </button>
        );
      })}
    </div>
  );
}

