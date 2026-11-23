# `STRATA_GFX12_EXP8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の RDNA4 デバイス（`gfx1200` / `gfx1201`）で、MoE expert の gate/up 処理に EXP mode 8 を自動選択するかを切り替える。未設定時は自動選択を許可し、この変数の値の先頭文字が `0` なら自動選択を止める。`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`、`engine/src/kernels/cuda/iq_kernels.cu:6750-6803`。

mode 8 が選択され、対象層の条件も満たすと、gate/up、SwiGLU、q8_1 量子化をまとめた fused gate/up kernel を使う。これは環境変数単独で全モデル・全層の kernel を強制するスイッチではない。`engine/src/kernels/cuda/iq_kernels.cu:7205-7239`。

## 値と判定

値は文字列として取得し、数値変換や文字列全体の比較はしない。`STRATA_GFX12_EXP8` 自体は `v12 != nullptr && v12[0] == '0'` のときだけ無効化する。したがって空文字、`1`、`true`、`false`、`0anything` はそれぞれ「設定ありだが先頭文字が `0` ではない」「無効化条件ではない」「無効化条件ではない」「無効化条件ではない」「無効化」となる。大文字小文字、後続文字、空白は判定されない。`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-726,731-743`。

| 条件 | unset | 自動選択を許可する値 | 自動選択を止める値 |
|---|---|---|---|
| 現在デバイスが `gfx1200` / `gfx1201` で、グローバル停止条件なし | 許可 | 空文字、`1`、`true`、`false`、`1anything` など、先頭文字が `0` ではない任意の文字列 | `0`、`0anything`、`0 false` など、先頭文字が `0` の文字列 |
| 他の GCN arch | この変数は参照されず、当該 arch 用の別条件で判定 | 該当なし | 該当なし |

`STRATA_HIP_EXP8` が設定されていて先頭文字が `0` の場合は、`STRATA_GFX12_EXP8` の値に関係なく自動選択を止める。先頭文字が `0` でない `STRATA_HIP_EXP8` は全体を強制 ON にするものではなく、arch ごとの判定に進む。`engine/src/kernels/hip/hip_unsloth_wmma.cu:721-743`。

## 有効になる条件

- `engine/cmake/strata_gpu_engine.cmake:107-112` により HIP ビルドでこの実装が組み込まれ、通常の HIP (`__HIPCC__` かつ `STRATA_HIP_GFX906` ではない) の EXP mode 経路を通ること。`engine/src/kernels/cuda/iq_kernels.cu:6755-6761`。gfx906 用 HIP 互換 backend ではこの判定関数を使わない。
- 実行中のデバイス情報取得が成功し、デバイス番号が `0..63` の範囲内であること。範囲外または `hipGetDeviceProperties` の失敗時は `false` となる。`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`。
- arch 名が `gfx1200` または `gfx1201` であること。GFX12 判定 helper はこの 2 名だけを対象にする。`engine/include/strata/kernels/hip_unsloth_wmma.hpp:47-49`。
- `STRATA_EXP_MODE` が非負の値として解釈される場合は、その値が自動判定より優先される。たとえば `STRATA_EXP_MODE=8` はこの変数で自動選択を止めても mode 8 を選び得る。逆に `STRATA_EXP_MODE=0` は自動判定が許可でも mode 0 にする。`STRATA_EXP_MODE` の値は `atoi` で変換され、設定時の変換結果が 0 以上なら採用される。内部 bench override `g_exp_mode >= 0` はそれより先に採用される。`engine/src/kernels/cuda/iq_kernels.cu:6763-6803`。
- 自動 mode 判定が呼ばれる grouped expert 経路であること。`grid_groups > 0 && grid_groups < cap_groups` のときは `exp_mode()` ではなく mode 0 が選ばれる。`engine/src/kernels/cuda/iq_kernels.cu:7196-7203`。
- fused gate/up の実行には、`STRATA_EXP_LAYOUTS` が有効、nibble layout ではない、`L.had_block == 0`、`L.n_embd <= 4096`、`L.n_ff % 32 == 0`、かつ gate/up の型がコード列挙の対象型であることが必要。条件を満たさない層では fused gate/up は使われず、後続の通常または LDS 経路へ進む。`engine/src/kernels/cuda/iq_kernels.cu:5883-5898,7205-7214,7265-7316`。
- mode 8 の自動選択は EXP mode の既定値 0 を切り替える。別の EXP mode が選ばれた場合や該当する処理経路に入らない場合、この変数だけでは mode 8 を強制しない。mode 8 を明示する `STRATA_EXP_MODE` との優先関係は上記のとおり。`engine/src/kernels/cuda/iq_kernels.cu:6763-6803,7196-7214`。

## 実行時の詳細

`hip_exp8_auto_enabled(dev)` の初回判定時に `STRATA_HIP_EXP8`、`STRATA_GFX1151_EXP8`、`STRATA_GFX11_EXP8`、`STRATA_GFX12_EXP8`、`STRATA_GFX11_DEFAULTS`、`STRATA_GFX1030_EXP8` を読み、デバイス arch ごとの結果を `static std::atomic<int> cache[64]` に保存する。GFX12 ではグローバル停止を確認した後、`gfx1200` / `gfx1201` の場合に限り `STRATA_GFX12_EXP8` の先頭文字を判定する。したがって、この関数のキャッシュ確定後にプロセス環境を変更しても、そのデバイスの判定結果には反映されない。`engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748`。

`exp_mode()` 側も `STRATA_EXP_MODE` の `atoi` 結果を関数内 `static const int` に保存し、デバイスごとの自動 mode を `per_dev[64]` に保存する。こちらも初回評価後の環境変更は反映されない。mode 8 の選択後も、expert layout と層の条件により fused gate/up が選ばれない経路がある。`engine/src/kernels/cuda/iq_kernels.cu:6763-6803,7205-7239`。

この変数は down kernel の選択にも別途参照される。`L.d_type == 20` の場合は `gfx1151_exp8(dev_d)` が false なら `lds_down_ok` 条件を満たさず、true なら他の条件次第で LDS down kernel 候補になる。この判定は `STRATA_EXP_MODE` の明示値とは別に helper の結果を使う。`engine/src/kernels/cuda/iq_kernels.cu:7355-7385`。

## ログと測定値

通常の処理経路では、この環境変数の有効・無効を示す専用の警告やログは見つからなかった。arch 情報の取得失敗や対象外 arch は `false` として扱われ、mode 8 自動選択の fallback に進む。明示 mode 8 と自動選択の結果は分かれ得る。`engine/src/kernels/hip/hip_unsloth_wmma.cu:728-748`、`engine/src/kernels/cuda/iq_kernels.cu:6763-6803`。

ソース内の検証用実行ファイルは `EXP8_AUTO=%d` を表示するが、通常の Strata 実行ログではない。`engine/src/kernels/hip/hip_unsloth_verify.cu:425-427`。この環境変数について `docs/DETAILS.md` に条件付きの測定値は見当たらないため、性能値は記載しない。

## 根拠

- `engine/src/kernels/hip/hip_unsloth_wmma.cu:716-748` — 環境変数の全読み取り、GFX12 判定、優先条件、cache。
- `engine/include/strata/kernels/hip_unsloth_wmma.hpp:42-52` — 対象 arch 名。
- `engine/cmake/strata_gpu_engine.cmake:107-112` — HIP 時の実装組み込み。
- `engine/src/kernels/cuda/iq_kernels.cu:6750-6803` — HIP guard、EXP mode と明示値の優先、mode の cache。
- `engine/src/kernels/cuda/iq_kernels.cu:7196-7239,7355-7385` — grouped expert 呼び出し、fused gate/up および down 経路の条件。
- `docs/SETTINGS.md:377` — 変数の候補一覧上の分類は `text`、適用先は AMD。挙動の説明は上記ソースを根拠にした。
