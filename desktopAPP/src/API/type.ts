export interface NavItem {
  id: string;
  label: string;
  icon: string;
};

export interface SkinData {
    id: number;
    name: string;
    price: number;
}

declare global {
  interface Window {
    desktopAPI: { // Убираем знак вопроса здесь, если API внедряется всегда
      appName: string;
      version: string;
      navigateTo: (page: string) => void;
      dockerAction: (action: string, service: string) => Promise<{ ok?: boolean; error?: string }>;
      dockerStatus: () => Promise<any[]  | { error: string }>;
      dockerLogs: (service: string) => Promise<{ ok?: boolean; stdout?: string; stderr?: string; error?: string }>;
    };
  }
}

export {};