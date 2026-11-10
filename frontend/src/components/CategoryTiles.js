import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";

const CATEGORIES = [
  {
    name: "Walking Vests",
    blurb: "Soft, lightweight vests that move pressure from neck to chest.",
    frames: [
      "/images/brand/vest-plaid.webp",
      "/images/brand/vest-red.webp",
      "/images/brand/vest-plaid-zoom.webp",
      "/images/brand/vest-red-zoom.webp",
    ],
  },
  {
    name: "Step-In Harnesses",
    blurb: "Choke-free and on in seconds with one-click closures.",
    frames: [
      "/images/brand/harness-green.webp",
      "/images/brand/harness-green-zoom.webp",
      "/images/brand/harness-green.webp",
      "/images/brand/harness-green-zoom.webp",
    ],
  },
  {
    name: "Designer Collars",
    blurb: "Premium cotton, reinforced for strength, gentle on necks.",
    frames: [
      "/images/brand/collar-red.webp",
      "/images/brand/collar-camo.webp",
      "/images/brand/collar-red-zoom.webp",
      "/images/brand/collar-camo-zoom.webp",
    ],
  },
  {
    name: "Matching Leashes",
    blurb: "Coordinated leads that complete every set beautifully.",
    frames: [
      "/images/brand/leash-ladybug.webp",
      "/images/brand/leash-ladybug-zoom.webp",
    ],
  },
];

function GlitchImage({ frames, alt, active }) {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    if (!active) {
      setFrame(0);
      return;
    }
    const id = setInterval(() => setFrame((f) => (f + 1) % frames.length), 450);
    return () => clearInterval(id);
  }, [active, frames.length]);

  return (
    <div className={`relative h-full w-full ${active ? "glitch-jitter" : ""}`}>
      {frames.map((src, i) => (
        <img
          key={`${i}-${src}`}
          src={src}
          alt={i === 0 ? alt : ""}
          loading="lazy"
          className={`absolute inset-0 h-full w-full object-contain p-6 transition-opacity duration-300 ease-out ${i === frame ? "opacity-100" : "opacity-0"} ${
            !active && i === 0 ? "transition-transform duration-700 ease-out group-hover:scale-105" : ""
          }`}
        />
      ))}
      {active && <div className="glitch-scan pointer-events-none absolute inset-0" />}
    </div>
  );
}

function CategoryTile({ cat, index }) {
  const [active, setActive] = useState(false);
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, delay: index * 0.1 }}
    >
      <Link
        to={`/shop?category=${encodeURIComponent(cat.name)}`}
        data-testid={`category-tile-${cat.name.toLowerCase().replace(/\s+/g, "-")}`}
        className="group block"
        onMouseEnter={() => setActive(true)}
        onMouseLeave={() => setActive(false)}
      >
        <div className="relative aspect-[3/4] overflow-hidden rounded-3xl bg-white" data-testid={`category-glitch-${cat.name.toLowerCase().replace(/\s+/g, "-")}`}>
          <GlitchImage frames={cat.frames} alt={cat.name} active={active} />
          <div className="absolute right-4 top-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-[#FDF7FA] text-[#3E2A33] opacity-0 shadow-md transition-opacity duration-300 group-hover:opacity-100">
            <ArrowUpRight className="h-4 w-4" />
          </div>
        </div>
        <h3 className="font-serif-display mt-5 text-xl font-semibold text-[#3E2A33] transition-colors group-hover:text-[#E6007E]">
          {cat.name}
        </h3>
        <p className="mt-1.5 text-sm leading-relaxed text-[#5A6572]">{cat.blurb}</p>
        <span className="mt-3 inline-block text-sm font-semibold text-[#E6007E]">
          Shop {cat.name.toLowerCase()} →
        </span>
      </Link>
    </motion.div>
  );
}

export default function CategoryTiles() {
  return (
    <section data-testid="category-tiles" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:py-28">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.7 }}
        className="mb-12 max-w-xl"
      >
        <p className="font-mono-accent mb-3 text-xs tracking-[0.3em] text-[#E6007E]">THE COLLECTION</p>
        <h2 className="font-serif-display text-3xl font-semibold tracking-tight text-[#3E2A33] sm:text-4xl">
          Shop our signature pieces
        </h2>
        <p className="mt-4 text-base leading-relaxed text-[#5A6572] sm:text-lg">
          Designed with love, made for real dogs — every piece keeps the walk gentle and the look unforgettable.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {CATEGORIES.map((cat, i) => (
          <CategoryTile key={cat.name} cat={cat} index={i} />
        ))}
      </div>
    </section>
  );
}
