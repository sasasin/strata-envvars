# `STRATA_SPLIT_CHUNK16K`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。対象は Strata 所有ソースと関連文書。

## 役割

AMD gfx12 の単一 GPU 実行で既定値が 16,384 token に引き上げられた prefill 自動 chunk 上限を、layer split（複数 GPU）でも維持するための opt-in 変数です。未設定または整数変換結果が 0 の場合、複数 GPU split では上限を 8,192 token に戻します。有効にするとこの split 時の縮小を行わず、16,384 の上限を保ちます。

これは上限の選択に関わるもので、chunk を必ず 16,384 に固定する設定ではありません。後続の prefill 計画が cache、buffer、context などの条件を調べ、適合するより小さい chunk を選ぶ場合があります。

## 値と判定

実装は `std::getenv` で値を取り、`std::atoi` の結果が 0 でないかを判定します。文字列全体の検証や `true` / `false` の特別扱いはありません。

| 値 | split 時の動作 |
|---|---|
| 未設定 | 無効。上限を 8,192 に縮小 |
| 空文字 | `atoi("") == 0` のため無効。上限を 8,192 に縮小 |
| `0`、`0tail`、非数値文字列（例: `true`） | 変換結果が 0 のため無効 |
| `1`、`2tail`、`-1` など、先頭の整数変換結果が非 0 | 有効。split による 8,192 への縮小を行わない |

したがって `STRATA_SPLIT_CHUNK16K=true` は有効化しません。一方、先頭に数値がある `1anything` は整数変換結果が 1 なので有効です。値域の検証、clamp、エラー出力はありません。整数の範囲外の入力に対する `atoi` の結果は、この実装で別途定義されていません。

`getenv` の戻り値ポインターは該当ブロックに初めて到達した時点で関数内 `static` に保存されます。判定時にはそのポインターの文字列を `atoi` に渡します。新たに `getenv` を呼び直す仕組みはありません。

根拠: `src/program/generate.cpp:6620-6626`。

## 有効になる条件

以下をすべて満たす経路だけが対象です。

- Linux HIP ビルド（`STRATA_USE_HIP` が定義され、`_WIN32` が未定義）。gfx12 の 16K 既定値を立てるコード自体がこのビルド条件内にあります。
- `--prefill auto` を指定し、`STRATA_PREFILL_AUTO_MAX` で上限を明示していないこと。`--prefill auto:N`、明示的な `--prefill N`、`STRATA_PREFILL_AUTO_MAX` を使った自動設定では gfx12 の「裸の auto」既定処理が有効になりません。
- `STRATA_GFX12_CHUNK` と `STRATA_GFX12_DEFAULTS` が先頭文字 `0` で無効化されておらず、GPU 0 のアーキテクチャ名が `gfx_arch_is_gfx12()` に該当すること。
- split が実際に複数 GPU を使うこと。同一 GPU 指定や `--split-skip-if-fits` によって split が取り消された場合は対象外です。

これらを満たして gfx12 の 16K 既定値が選ばれた後、`STRATA_SPLIT_CHUNK16K` が非 0 なら split 用の縮小をスキップします。0 相当なら `auto_ceiling`、`o.prefill_auto_max`、`o.prefill_chunk` をそれぞれ最大 8,192 にします。後者2項目は後の chunk 選択経路にも上限を伝えます。単一 GPU や gfx12 以外では、この変数を設定してもコード上の効果はありません。

根拠: `src/program/generate.cpp:2256-2272,2407,3470-3480,6616-6626`。

## 実行時の詳細

gfx12 の裸の `--prefill auto` では、Linux HIP の gfx12 デバイスについて `prefill_auto_max` と初期 `prefill_chunk` が 16,384 に設定されます。split が残っている場合、`STRATA_SPLIT_CHUNK16K` の整数変換結果が 0 なら、split prompt は pipeline で複数 chunk を流せるよう、これらの値を 8,192 以下に縮めます。非 0 ならこの処理を省きます。その後の auto chunk 計画は、上限内で context や prefill buffer / cache の適合性を確認して最終 chunk を決めます。

この変数専用のログ、警告、エラー、終了処理はありません。上限変更は prompt の chunk 計画に作用します。Strata の `docs/MULTI_GPU.md` は gfx12 split の既定 chunk を 8,192 と説明し、`STRATA_SPLIT_CHUNK16K=1` で 16,384 を保つと記載しており、実装と一致します。同文書は R9700 の複数 prompt 長に対する性能差も報告していますが、該当箇所に測定手順の詳細はないため、その数値を一般的な性能保証とは扱いません。

根拠: `src/program/generate.cpp:6612-6626,6661-6697`; `docs/MULTI_GPU.md:196-200`。
