# `STRATA_PF_TILE_DEBUG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

fused prefill の native expert kernel が自動 tile rule を使って work item を選んだとき、その選択を stderr に出す診断用スイッチである。tile 選択や fused kernel の有効化自体は変えず、`pick_ww()` が得た `pk.ww` をそのまま返す。`ww=2` は routed row 128、`ww=4` は routed row 64 を表す（`engine/src/prefill/moe_fused_iq.cu:3336-3352`、`engine/include/strata/prefill/fused_tile_rule.hpp:35-39`）。

読み取りと出力は `engine/src/prefill/moe_fused_iq.cu` の `pick_ww()` にある。通常形状の fused expert 実装に加え、同ファイルを Qwen3.6 用 namespace で再コンパイルするコピーもこのコードを使う（`engine/src/prefill/moe_fused_iq_q36.cu:1-8,33-36`）。これは fused prefill が選ばれた後の診断であり、通常の MMQ 経路などでは読み取られない（同 `moe_fused_iq.cu:3355-3374,3867`）。

## 値と判定

`std::getenv()` の結果が null でなく、先頭文字が `'1'` なら有効。文字列全体の parse・比較はせず、空文字の特別扱いもない（空文字は設定済みだが `v[0]` が NUL なので無効）。空白除去、大文字小文字変換、数値範囲検査もない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `pick_ww()` 内の自動 rule 分岐 | 無効 | `1`, `1anything` | 空文字, `0`, `true`, ` 1`, `0anything` |

判定は数値の真偽ではなく先頭文字だけを見るため、`10` や `1false` も有効である。無効値は warning にならず、デバッグ行が出ない。CLI 引数によるこの変数の上書きは実装にない。別環境変数 `STRATA_PF_FUSED_TILE` の `atoi()` 結果が 64 または 128 なら自動 rule を通らず、このデバッグ判定にも到達しない（`engine/src/prefill/moe_fused_iq.cu:3327-3345`）。

## 有効になる条件

- fused native prefill の起動経路が `launch_ww()` から `pick_ww()` を呼ぶこと。これは tile のログだけを有効にし、fused prefill 自体を有効化しない。どの layer が native fused 経路を使うかは別の対応形式・デバイス・設定条件で決まる（`engine/src/prefill/moe_fused_iq.cu:3355-3374,3867`）。
- 自動 rule の結果 `pk.why` が `Why::kBand` 以外であること。通常の 56–112 rows/expert の band 選択はログ対象外。rule 固有の対象は GPU class、SM 数、routed rows、expert 数、staging 状態、quant pair による（`engine/include/strata/prefill/fused_tile_rule.hpp:42-106`）。
- 早期 return に入らないこと。`STRATA_PF_FUSED_TILE=64` または `128` の強制指定、CUDA の Turing (`dv.t75`) 経路、CUDA の staged blob check 失敗による unstaged fallback は `pick_ww()` の診断分岐より先に戻る（`engine/src/prefill/moe_fused_iq.cu:3327-3334,3358-3373`）。
- そのビルドで `moe_fused_iq.cu` が実装として使われること。CUDA/HIP 用の CMake backend が同ファイルをビルド対象にする。SYCL の `moe_fused_stub.cpp` は stub で、この読み取り箇所を含まない（`engine/cmake/backends/cuda.cmake:135-136`、`engine/cmake/backends/hip.cmake:34-37`、`engine/sycl/src/prefill/moe_fused_stub.cpp:1-12`）。Qwen3.6 用コピーでは CUDA および gfx12 HIP の実装に同じ読み取りコードが含まれる（`engine/src/prefill/moe_fused_iq_q36.cu:1-8,33-36`）。

## 実行時の詳細

環境値を読むのは、`pk.why != Why::kBand` となる `pick_ww()` 呼び出しが初めて起きた時である。読み取りはブロック内の関数ローカル `static const bool` に保存され、以後同じコンパイル単位の呼び出しでは再読込しない。そのため実行中に環境値を変更しても、そのコピーの判定には反映されない。Qwen3.6 用コピーは元ソースを別 namespace で再コンパイルするので、コピーごとに別の static cache を持つ（`engine/src/prefill/moe_fused_iq.cu:3344-3352`、`engine/src/prefill/moe_fused_iq_q36.cu:1-8,33-36`）。

`pick_ww()` は rule の `Pick` を計算した後にだけ診断判定を行う。値が有効で条件を通れば、該当する各起動で rows、experts、平均 rows/expert、rule class と選択された `ww` を出力する。デバッグ変数によって処理を終了したり、選択や出力値を書き換えたりする経路はない（`engine/src/prefill/moe_fused_iq.cu:3341-3352`）。

## ログと測定値

有効値かつ自動 rule の非-band 分岐では、stderr に次の形式を出す。出力は選択ごとに1行で、`cls` は `s121`、`s120 small`、`staged`、`s86 wide`、`s86 kq`、`s120 kq`、または `s120` のいずれかである（`engine/src/prefill/moe_fused_iq.cu:3344-3350`）。

```text
strata: fused tile: rows <n> experts <n_expert> avg <平均値> <cls> yes -> ww <2 または 4>
```

この変数自身による警告、エラー、終了コード変更はない。既定値のまま、band rule、強制 tile、早期 return の場合は上記行を出さない。tile rule header には別途測定記録があるが、この診断変数の性能効果を示す測定ではないため、本書では性能値を主張しない（`engine/include/strata/prefill/fused_tile_rule.hpp:4-14,42-106`）。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:3327-3352` — `STRATA_PF_FUSED_TILE` による早期 return、対象変数の読み取り・cache・stderr 出力・選択値の return。
- `engine/src/prefill/moe_fused_iq.cu:3355-3374,3867` — launch から `pick_ww()` への経路と CUDA early return。
- `engine/include/strata/prefill/fused_tile_rule.hpp:35-39,42-106` — tile の対応と自動 rule。
- `engine/src/prefill/moe_fused_iq_q36.cu:1-8,33-36` — Qwen3.6 用の別コンパイルコピー。
- `engine/cmake/backends/cuda.cmake:135-136`、`engine/cmake/backends/hip.cmake:34-37`、`engine/sycl/src/prefill/moe_fused_stub.cpp:1-12` — backend ごとの実装配置。
