import './StatusTag.css';

const STATUS_MAP = {
  pending: { label: '待解析', className: 'status-pending' },
  parsing: { label: '解析中', className: 'status-parsing' },
  completed: { label: '已完成', className: 'status-completed' },
  failed: { label: '解析失败', className: 'status-failed' },
};

export default function StatusTag({ status }) {
  const info = STATUS_MAP[status] || STATUS_MAP.pending;
  return (
    <span className={`status-tag ${info.className}`}>
      {info.label}
    </span>
  );
}
