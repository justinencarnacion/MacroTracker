import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { pages, type PageRoute } from "./pages/registry";

function TitledPage({ page }: { page: PageRoute }) {
  useEffect(() => {
    document.title = page.title;
  }, [page.title]);
  return page.element;
}

export function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Layout>
        <Routes>
          {pages.map((page) => (
            <Route key={page.path} path={page.path} element={<TitledPage page={page} />} />
          ))}
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
