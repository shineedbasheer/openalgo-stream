// src/components/ConfirmationModal.tsx

import React from 'react';
import { X, AlertCircle } from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';

export interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
type?: "publish" | "test" | "warning" | "danger" | "create";}

const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  type = 'publish'
}) => {
  // const { theme } = useTheme();
  const { mode } = useThemeStore()
  

  if (!isOpen) return null;

  const textClass = mode === 'dark' ? 'text-white' : 'text-gray-900';
  const cardBg = mode === 'dark' ? 'bg-gray-800' : 'bg-white';
  const subTextClass = mode === 'dark' ? 'text-gray-400' : 'text-gray-600';

  const getButtonColor = () => {
    switch (type) {
      case 'publish':
        return 'bg-blue-600 hover:bg-blue-700';
      case 'test':
        return 'bg-purple-600 hover:bg-purple-700';
      case 'warning':
        return 'bg-yellow-600 hover:bg-yellow-700';
      case 'danger':
        return 'bg-red-600 hover:bg-red-700';
      default:
        return 'bg-blue-600 hover:bg-blue-700';
    }
  };

  return (
    <div className="fixed inset-0 z-[66] flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 backdrop-blur-md bg-transparent"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className={`relative ${cardBg} rounded-xl shadow-2xl w-full max-w-md mx-4 p-6 animate-scale-in`}>
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              type === 'danger' || type === 'warning' ? 'bg-red-100 dark:bg-red-900' : 'bg-blue-100 dark:bg-blue-900'
            }`}>
              <AlertCircle className={
                type === 'danger' || type === 'warning' ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'
              } size={20} />
            </div>
            <h3 className={`text-lg font-bold ${textClass}`}>
              {title}
            </h3>
          </div>
          <button
            onClick={onClose}
            className={`p-1 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors`}
          >
            <X size={20} className={textClass} />
          </button>
        </div>

        {/* Message */}
        <p className={`${subTextClass} mb-6`}>
          {message}
        </p>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className={`flex-1 px-4 py-2 rounded-lg font-medium transition-colors ${
              mode === 'dark'
                ? 'bg-gray-700 hover:bg-gray-600 text-white'
                : 'bg-gray-200 hover:bg-gray-300 text-gray-900'
            }`}
          >
            {cancelText}
          </button>
          <button
            onClick={() => {
              onConfirm();
              onClose();
            }}
            className={`flex-1 px-4 py-2 rounded-lg font-medium text-white transition-colors ${getButtonColor()}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmationModal;