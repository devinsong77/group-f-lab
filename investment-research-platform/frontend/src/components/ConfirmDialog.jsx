import './ConfirmDialog.css';

export default function ConfirmDialog({ visible, title, message, onConfirm, onCancel }) {
  if (!visible) return null;
  return (
    <div className="confirm-overlay">
      <div className="confirm-dialog">
        <h3 className="confirm-title">{title || '确认操作'}</h3>
        <p className="confirm-message">{message}</p>
        <div className="confirm-actions">
          <button className="confirm-btn-cancel" onClick={onCancel}>取消</button>
          <button className="confirm-btn-ok" onClick={onConfirm}>确认</button>
        </div>
      </div>
    </div>
  );
}
