# `STRATA_WARM_GRAPHS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の `strata generate` が speculative decoding に入るとき、Verifier の各 window サイズの graph と、MTP drafter が使う graph 群をその時点で先に capture します。無効にするとこの先行 capture を省き、各 graph は従来どおり必要になった時点で capture されます。主に初回 window／初回 request の capture 時間を前払いするための設定です。

## 値と判定

`sycl/src/program/generate.cpp` は `getenv()` の値を文字列全体ではなく先頭文字 `v[0]` だけで判定します。

| 値 | 判定 | 備考 |
|---|---|---|
| unset | 有効 | 既定で warm を実行 |
| 空文字 | 有効 | `getenv()` は非 null、先頭は `\0` なので `'0'` ではない |
| `0` で始まる値 | 無効 | `0`, `0anything` など |
| それ以外の設定値 | 有効 | `1`, `true`, `false`, 空白始まりなど。数値 parse や大文字小文字の比較はしない |

判定は speculative decoding ブロック内の関数ローカル `static const bool` に保存されます。プロセス内で初回にそのブロックへ入ったときに評価され、以後の環境変更は再評価されません。根拠: `sycl/src/program/generate.cpp:12259-12264`。

## 有効になる条件

この読み取り箇所は SYCL 実装にあります。通常の非 speculative 生成経路では該当ブロックに入りません。speculative decoding が始まるには `--spec` が有効で、prompt 側の通常生成から `spec_pos` が設定され、生成上限到達や EOS 終了などで先に処理が終わっていない必要があります（`sycl/src/program/generate.cpp:12020-12031`）。

## 実行時の詳細

値が有効なら、speculative loop に入る直前に `ver.warm(err)` を呼びます。`Verifier::warm()` は `T=1..max_t_` の各 window サイズについて `capture(T, err)` を実行します（`sycl/src/program/generate.cpp:12263-12272`, `sycl/src/core/verify.cpp:2744-2750`）。`use_mtp` が真、つまり MTP drafter がある場合だけ `mtp.warm(err)` も実行され、round/prefill graph と必要な step graph を capture します（`sycl/src/program/generate.cpp:12266`, `sycl/include/strata/core/mtp.hpp:52-59`）。MTP を使わない場合は drafter の warm はありません。

warm 中にいずれかの capture が失敗すると、stderr に `strata generate: warm-up capture: <error>` を出して `strata generate` は status 1 で終了します。成功すると stderr に `strata generate: window and draft graphs captured in %.0f ms` を出します（`sycl/src/program/generate.cpp:12265-12271`）。

`STRATA_VERIFY_EAGER` が設定されている場合、Verifier の `capture()` は実際の graph capture を行わず成功扱いにするため、`ver.warm()` を呼んでも Verifier graph は作られません（`sycl/src/core/verify.cpp:1734-1742`）。また、warm を無効にした場合も、最初の window で必要になった graph は `capture()` 側から遅延 capture されます（同 `1734-1747`）。この変数は capture のタイミングを変えるもので、実行可否を単独で保証する設定ではありません。

## 文書との照合

`docs/INTEL.md:278-285` は、B70 の記載条件において graph を先行 capture する変更により、最初の request で 250–290 ms の capture を負担しなくなったと説明しています。同表は同じ prompts の測定に関する記述ですが、`STRATA_WARM_GRAPHS` 単独の性能比較値ではありません。数値はこの資料に書かれた環境での説明であり、他の環境での所要時間を示すものではありません。コードの注釈は server ではこの capture を process あたり一度払うとしています（`sycl/src/program/generate.cpp:12260-12261`）。

## 根拠

- `sycl/src/program/generate.cpp:12020-12031` — speculative decoding への遷移条件。
- `sycl/src/program/generate.cpp:12257-12272` — 環境変数の判定、warm 呼び出し、ログと失敗処理。
- `sycl/src/core/verify.cpp:1734-1747,2744-2750` — Verifier graph の遅延 capture と warm 実装。
- `sycl/include/strata/core/mtp.hpp:52-59` — MTP graph の warm 対象。
- `docs/INTEL.md:278-285` — B70 条件での関連測定説明。
