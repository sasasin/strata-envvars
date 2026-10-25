# `STRATA_DS4_HIPK`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 の DS4 i-quant expert set 計算で、HIP gfx12 向け WMMA カーネルを使用するか、また使用時に重みをどこへ展開するかを制御します。通常は gfx12 で WMMA カーネルが有効です。値の先頭が `0` ならこの経路を無効にし、従来の set kernel へ進みます。`atoi()` の結果が `2` の場合は WMMA の shared-memory 重みカーネルを選び、それ以外では重みをレジスタで扱うカーネルを選びます。

## 値と判定

| 設定値 | gfx12 WMMA 経路 | WMMA 内の方式 |
|---|---|---|
| 未設定 | 有効 | レジスタ方式（`atoi` の既定値 0） |
| 空文字 | 無効（先頭文字が `\0`） | 到達しない |
| 先頭文字が `0` | 無効 | 到達しない |
| `atoi()` が `2` になる値（例: `2`, `2abc`） | 有効 | shared-memory 方式 |
| その他（例: `1`, `3`, `abc`, `-2`） | 先頭が `0` でなければ有効 | レジスタ方式 |

判定は一貫した真偽値 parse ではありません。デバイス可否判定は先頭文字だけを見て `0` を除外し、別の判定は `atoi()` で整数の先頭部分を読みます。したがって `02` は先頭判定で無効、`2abc` は shared-memory 方式、`abc` は有効なレジスタ方式になります。空白や大文字小文字の正規化はありません。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` でビルドされた `strata-dsv41` の DS4 経路であること。CMake ではこのターゲットは既定でビルドされません。
- HIP ビルドであること（`ds4_iq_hip.inc` は `STRATA_USE_HIP` の場合だけ含まれます）。実行中のデバイス名が `gfx12` で始まる必要があります。
- IQ 対応形式（IQ2_XXS/XS/S、IQ3_XXS/S、IQ4_XS、IQ1_S/M、IQ4_NL）の gate/up または down set kernel であること。TQ 形式は別経路です。
- expert 行数 `a.max_rows` が16より大きく、次元・stride・アドレス整列が実装の条件を満たすこと。`K` は256の倍数、`N` は64の倍数、`ldx` は8の倍数、`ldo` は2の倍数で、入力ポインターは16-byte aligned が必要です。さらに選択したタイル幅で `N` が割り切れない場合も専用 launch は失敗扱いとなり、呼び出し元の通常 set kernel に戻ります。
- 対応する AMD gfx12 の WMMA 組み込み命令を含む HIP 用ターゲットであること。組み込み関数は `__gfx1200__` / `__gfx1201__` でないコンパイル時には積和を行わず、入力 accumulator を返します。

値が有効でも以上の条件を満たさなければこの経路は使われません。

## 実行時の詳細

`ok_device()` は GPU ごとの `static std::atomic<int>` に判定を保存します。各 GPU で最初にこの判定を通った後に環境変数を変更しても、その GPU の gfx12 可否は再評価されません。gfx12 で、対応型かつ `max_rows > 16`、shape/alignment 条件を通過した場合に限り、関数テンプレートごとの `static` 値として `atoi(STRATA_DS4_HIPK)` を読みます。この値が `2` なら shared-memory 重みカーネル、そうでなければレジスタ重みカーネルを選びます。設定変更はそれぞれの static 判定後には反映されません。

レジスタ方式では別変数 `HIPK_CFG` が読み取られ、値1〜5かつ `max_rows <= 32` のときに対応するタイル構成を選びます。それ以外は行数に応じた既定タイル構成です。これは `STRATA_DS4_HIPK` の説明対象外の相互作用として記載しています。

環境変数によるログや警告はこの経路にはありません。専用 launch が条件不一致または launch error で `false` を返す場合、`launch_set()` は共通の WMMA（CUDA の場合）または通常の set kernel を選択します。

## 根拠

- `src/dsv41/ds4_iq_hip.inc:18-20,220-270` — 対象形式、デバイス判定、環境値の parse、tile 選択。
- `src/dsv41/ds4_iq_hip_r.inc:168-176` — レジスタ重み方式の grid 条件と launch。
- `src/dsv41/ds4_iq.cu:1177-1194,1408-1455` — HIP 専用 include、set kernel dispatch と fallback。
- `src/dsv41/ds4_iq.cu:1101-1116` — DS4 i-quant dispatch 対象形式。
- `src/dsv41/ds4_iq_hip.inc:22-27` — WMMA 組み込み関数のコンパイル時 architecture 条件。
- `CMakeLists.txt:797-811` — `STRATA_BUILD_DSV41` は既定 OFF、ON 時に `strata-dsv41` を構成。
- `cmake/hip_backend.cmake:94-108` — HIP ターゲットに `STRATA_USE_HIP=1` を定義。
- `docs/DETAILS.md:2491-2496` — gfx12 向け fused prompt expert の記述はありますが、`STRATA_DS4_HIPK` の値、挙動、測定結果は記載されていません。
