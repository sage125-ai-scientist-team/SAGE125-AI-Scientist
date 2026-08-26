import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type UserConfig } from "vite";

/**
 * Vite 配置：Streamlit Custom Component v2（React + TypeScript）。
 *
 * 关键点（均来自 Streamlit 官方 component-template v2 的约束）：
 * - `base: "./"`：保证从 Streamlit 组件 URL 提供服务时资源使用相对路径。
 * - `build.lib`：以库模式打包为单个 ES module 入口，产物带内容哈希
 *   （`index-<hash>.js` / `index-<hash>.css`），Python 侧用 glob 精确匹配一个文件。
 * - 不引入任何运行时 CDN：所有依赖（React、tsParticles、Magic UI 组件源码）
 *   都打包进本地构建产物。
 */
export default defineConfig(({ mode }): UserConfig => {
  const isDev = mode === "development";

  return {
    base: "./",
    plugins: [react(), tailwindcss()],
    define: {
      "process.env.NODE_ENV": JSON.stringify(isDev ? "development" : "production"),
    },
    build: {
      outDir: "build",
      emptyOutDir: true,
      sourcemap: isDev,
      minify: isDev ? false : "esbuild",
      lib: {
        entry: "./src/index.tsx",
        name: "Sage125Landing",
        formats: ["es"],
        fileName: () => "index-[hash].js",
      },
      rollupOptions: {
        output: {
          // 强制所有 CSS（包括组件内的局部样式）合并到一个带 hash 的文件，
          // 便于 Python 侧用单一 glob `index-*.css` 精确匹配。
          assetFileNames: "index-[hash][extname]",
          // CCv2 的 asset_dir glob（`index-*.js`）必须精确匹配到唯一一个
          // JS 文件；tsParticles 的动态 import 会被 Rollup 默认拆成多个
          // chunk，这里强制内联，产出单一 bundle。
          inlineDynamicImports: true,
        },
      },
    },
  };
});
