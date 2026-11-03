# `FNX_HC_BAR_WRAP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の hyper-connection (HC) grid barrier カウンターを、指定した回数の barrier の後に wrap する位置へ事前設定します。HC scratch を作成した各カードで HC 読み取りを行う前に一度設定され、barrier カウンターの wrap を検証するためのフックです。通常の利用者向け性能設定としての効果や、測定値はソースから確認できません。

## 値と判定

| 環境変数の状態・値 | 処理 |
|---|---|
| 未設定 | `getenv` 判定を通らず、カウンターへの事前設定をしません。`hc_prepare` がカウンターを 0 にします。 |
| 空文字 | 設定ありとして整数変換を行いますが、整数として拒否され、例外になります。既定値 0 には fallback しません。 |
| 10 進整数 | 符号は任意、数字のみの文字列を `strtoll(..., 10)` で全体変換します。変換範囲外、数字以外の末尾、空白、空文字は整数として拒否されます。 |
| 0、負数、または `4294967295` より大きい値 | `FNX_HC_BAR_WRAP: want a barrier count > 0, got <値>` で拒否されます。 |
| 正数 `n` | さらに `hc_preset_barrier` が、そのカードの barrier grid に対する上限 `hc_bar_mod(g) / g` を検査します。上限を超える場合は `hc_preset_barrier: barriers_left must be 1..<上限>` で拒否されます。 |

`env_int` 自体の未設定時既定値は 0 ですが、この変数では `getenv` が非 null のときだけ `env_int` を呼ぶため、明示設定値にその既定値は適用されません。`strtoll` の変換後に全体が消費されたことと `ERANGE` でないことを確認します。`hc_preset_barrier` の上限は各カードで得た grid サイズ `g` に依存します。

根拠: `src/split/src/engine.cu:142-145`, `src/split/src/env.hpp:15-21,33-40`, `src/split/src/kernels.cu:1233-1239`, `src/split/src/hc.cuh:26-28`。

## 有効になる条件

- `src/split/src/engine.cu` の `fnx::Engine` を含む実行経路で使われます。通常の `strata` 実行全体の設定ではありません。`strata-split` は `STRATA_BUILD_SPLIT` が opt-in で、Linux の CUDA または HIP ビルド時に限り追加されます（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-5,20-30,64-67`）。
- `sfnx` はモデルと MTP を読み込んだ後、`fnx::Engine` を構築します。その構築中に各カードの HC scratch を確保し、`hc_prepare` 後に環境変数を確認します（`src/split/tools/sfnx.cpp:1050-1060`, `src/split/src/engine.cu:31,114-145`）。同じ Engine 実装を利用するビルド済みの実行ファイルでも、この構築経路なら条件は同じです。
- CLI 引数や他の環境変数による上書き・優先順位はありません。値は要求時のカードごとの grid 上限を満たす必要があります。

## 実行時の詳細

HC scratch の最終 float を barrier カウンターとして使います。`hc_prepare` はカードの SM 数等から grid を決め、scratch のカウンターを 0 にします。環境変数が設定されている場合、Engine の構築中に `n` を読み、範囲検証後に `hc_preset_barrier` を呼びます。同関数は `mod = hc_bar_mod(g)`、`v = mod - n * g` を計算してカウンターへコピーします。HC 読み取りはこの同じ scratch のカウンターを使って grid barrier を実行します（`src/split/src/kernels.cu:1176-1193,1196-1230,1233-1239`; `src/split/src/kernels.hpp:56-74`; `src/split/src/hc.cuh:26-28,45,69-77`）。

値は static cache ではなく、Engine 構築時にカードごとに読み直されます。構築後の環境変更を再評価する経路はありません。複数カードの場合も各カードに個別の grid サイズが使われるため、全カードで上限を満たす値が必要です。

不正な整数または指定範囲外の値は Engine 構築を失敗させます。`sfnx` はこの例外を `ERR <理由>` として stdout に出し、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1055-1062,1027-1035`）。設定値が有効な場合に成功ログを出す処理は確認できません。

## 根拠

- `src/split/src/engine.cu:139-145` — HC scratch の確保、準備、変数の読み取り、値の検証と設定。
- `src/split/src/env.hpp:15-21,33-40` — 符号付き 10 進整数の全体 parse、未設定時既定値と parse エラー。
- `src/split/src/kernels.cu:1176-1193,1196-1239` — grid と counter 初期化、HC read、preset の上限・書き込み。
- `src/split/src/hc.cuh:26-28,69-77` — barrier modulo と grid barrier のカウンター処理。
- `src/split/src/kernels.hpp:56-74` — HC scratch と `hc_preset_barrier` の役割。
- `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-5,20-30,64-67` — split engine の opt-in と backend / OS 条件。
- `src/split/tools/sfnx.cpp:1027-1035,1050-1062` — 起動時の Engine 構築と例外時の観測可能な出力。
