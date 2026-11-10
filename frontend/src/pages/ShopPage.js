import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import ProductCard from "@/components/ProductCard";

const FILTERS = ["All", "Walking Vests", "Step-In Harnesses", "Designer Collars", "Matching Leashes"];

export default function ShopPage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [params, setParams] = useSearchParams();
  const active = params.get("category") || "All";

  useEffect(() => {
    api
      .get("/products")
      .then(({ data }) => setProducts(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(
    () => (active === "All" ? products : products.filter((p) => p.category === active)),
    [products, active],
  );

  return (
    <main data-testid="shop-page" className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:py-20">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="mb-10">
        <p className="font-mono-accent mb-3 text-xs tracking-[0.3em] text-[#E6007E]">THE FULL COLLECTION</p>
        <h1 className="font-serif-display text-4xl font-semibold tracking-tight text-[#3E2A33] sm:text-5xl">
          Every piece, gently made
        </h1>
      </motion.div>

      <div className="mb-10 flex flex-wrap gap-2" data-testid="shop-filters">
        {FILTERS.map((f) => (
          <button
            key={f}
            data-testid={`filter-${f.toLowerCase().replace(/\s+/g, "-")}`}
            onClick={() => setParams(f === "All" ? {} : { category: f })}
            className={`rounded-full border px-5 py-2.5 text-sm font-semibold transition-colors ${
              active === f
                ? "border-[#3E2A33] bg-[#3E2A33] text-[#FDF7FA]"
                : "border-[#3E2A33]/20 text-[#3E2A33] hover:border-[#E6007E] hover:text-[#E6007E]"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="py-20 text-center text-[#5A6572]" data-testid="shop-loading">Fetching the collection…</p>
      ) : visible.length === 0 ? (
        <div className="py-20 text-center" data-testid="shop-unavailable">
          <p className="font-serif-display text-xl text-[#3E2A33]">The collection couldn't load just now</p>
          <p className="mt-2 text-sm text-[#5A6572]">Please refresh the page in a moment — if it persists, write to us via the Contact page.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((product, i) => (
            <ProductCard key={product.slug} product={product} index={i} />
          ))}
        </div>
      )}
    </main>
  );
}
