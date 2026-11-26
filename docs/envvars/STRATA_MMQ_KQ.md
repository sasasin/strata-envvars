# `STRATA_MMQ_KQ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata はこの変数を、K-quant の prompt 処理に関係する設定として起動環境へ渡し、特定の GPU / モデル起動経路では未設定時に `1` を補います。Strata 所有コードに `STRATA_MMQ_KQ` の値を文字列比較・数値変換して機能を分岐する実装はなく、値の解釈や MMQ ライブラリ内部の実行動作はここでは断定しません。Strata が確認するのは主に「設定されているか」です。CUDA 起動ログは、この設定が K-quant expert の prompt 経路に関係すると説明しています（`engine/src/core/nv_defaults.cpp:287-299`、`engine/src/core/arch_defaults.cpp:373-386`）。

## 値と判定

Strata の既定値設定コードは `getenv` の結果が null かどうかだけを使い、設定済みなら値を上書きしません。空文字、`0`、`1`、`true`、`false`、`0anything` はいずれも Strata の既定値注入に対しては「設定済み」です。Strata は大文字小文字、空白、数値としての妥当性を検査しません。したがって次表の「無効」は、Strata が無効値と判定するという意味ではなく、Strata 自身に値の parse 判定がないことを示します（`engine/src/core/arch_defaults.cpp:374-379`、`engine/src/core/nv_defaults.cpp:312-321`、`engine/src/qwen35/q36_engine.cu:5424-5429`）。

| 経路 | 未設定 | 設定済みの値（例） | Strata が無効値として扱う値 |
|---|---|---|---|
| 通常の `strata`、CUDA の既定値対象 | 条件を満たすと `1` を設定 | 空文字、`0`、`true`、`0anything` を含め、値を保持 | 該当なし。値を parse しない |
| 通常の `strata`、Linux HIP gfx12 | gfx12 既定値が有効なら `1` を設定 | 同上 | 該当なし。値を parse しない |
| `strata-q36` | 起動時に `1` を設定 | 値を保持 | 該当なし。値を parse しない |
| セットアップ生成の Unsloth run config | UD-Q5_K_XL / UD-Q6_K_XL では config に `1` を設定 | config の値を子プロセスへ渡す | 該当なし。値を parse しない |

Strata 側では設定有無しか見ないため、例の各文字列が MMQ 実装にとって有効かどうかは Strata ソースからは確定できません。

## 有効になる条件

- **通常の CUDA `strata`**: 非 HIP / 非 Metal のビルドで、可視 CUDA デバイスが 1 台以上あり、最小 compute capability が 8.0 以上、`STRATA_DEFAULTS=026` が有効でなく、`STRATA_NV_KQ_DEFAULT` の先頭文字が `0` でないとき、Strata は未設定の `STRATA_MMQ_KQ` に `1` を設定します。`kNvKqDefaultOn` は `true` なので、`STRATA_NV_KQ_DEFAULT=1` は必要ありません。既に変数が設定されている場合は、どんな値でもそのままです（`engine/src/program/generate.cpp:4421-4428,4472-4488`、`engine/src/core/nv_defaults.cpp:264-273,312-321`、`engine/include/strata/core/nv_defaults.hpp:83-86`）。
- **Linux HIP gfx12**: HIP ビルドでデバイス情報が取得でき、アーキテクチャが gfx12 のときに gfx12 既定値候補が評価されます。`STRATA_GFX12_DEFAULTS` の先頭文字が `0`、または `STRATA_DEFAULTS` が厳密に `026` / `0.2.6` / `v0.2.6` のときは候補がなく、そうでなければ Linux で `STRATA_MMQ_KQ=1` が候補になります。Windows HIP は `kGfx12PromptDefaultsOn` が false のため、この既定値を追加しません。既存値は空文字を含め上書きしません（`engine/src/program/generate.cpp:4287-4320`、`engine/include/strata/core/gfx12_extra.hpp:54-68`、`engine/include/strata/core/gfx12_platform_defaults.hpp:10-16`、`engine/src/core/arch_defaults.cpp:373-386`）。
- **`strata-q36`**: `--model` が指定された後、OS に応じて未設定なら `1` を設定します。GPU 世代・backend・`MMQ::built()` の値による条件分岐はこの設定にありません（`engine/src/qwen35/q36_engine.cu:5420-5430`）。
- **セットアップ**: `family == "unsloth"` かつ model が `UD-Q5_K_XL` または `UD-Q6_K_XL` のとき、run config の `env` に `STRATA_MMQ_KQ: "1"` を入れます。UD-Q4_K_XL にはこの関数から設定しません。サーバーはプロセス環境を複製した後、run config の `env` を文字列化して上書きするため、config にこのキーがあれば親シェルの値より config 値が優先されます（`terminal/setup.py:4741-4759`、`terminal/strata_control/setup_config.py:433-440`、`terminal/serve/server.py:4007-4028`）。
- `strata` の CLI 引数に `STRATA_MMQ_KQ` の代替指定や優先順位を扱うコードは確認できません。通常の `strata` では、明示された値は GPU 既定値より優先されます。セットアップ生成 config はサーバー起動時に親環境を上書きします。
- コード上、CUDA / gfx12 の既定値注入は「K-quant expert を持つモデルか」の判定より前に行われます。CUDA の説明ログは、モデルの expert layout を読み込んだ後、K-quant 型が見つかった場合に限って出ます（`engine/src/program/generate.cpp:4422-4424,4487-4488,5412-5419`）。

## 実行時の詳細

通常の CUDA `strata` は起動時に可視 GPU の compute capability を調べ、最小値を使って既定値を決めます。既定値を追加した場合は、その後モデルの expert layout を確認し、Q4_K / Q5_K / Q6_K / Q5_1 のいずれかを含むときだけ、設定された prompt 経路の説明行を stderr に出します（`engine/src/program/generate.cpp:4421-4488,5412-5419`、`engine/src/core/nv_defaults.cpp:264-273,301-324`）。対象変数自体に static cache はありません。既定値設定関数が起動時に環境を確認し、未設定ならプロセス環境を書き換えます。対して `STRATA_DEFAULTS` の判定は `qwen_defaults_026()` の初回呼び出しで static cache されます（`engine/include/strata/core/defaults_026.hpp:21-30`）。

通常の HIP `strata` は起動時に GPU 情報から arch defaults を適用します。gfx12 の Linux では候補 env の設定有無を確認し、未設定のものだけを書き込みます。`strata-q36` も起動時に未設定なら同じ値を環境へ設定し、その後のモデル処理に進みます。どちらも、この変数の値をリクエストごとに読み直す処理はありません（`engine/src/program/generate.cpp:4287-4320`、`engine/src/core/arch_defaults.cpp:373-386`、`engine/src/qwen35/q36_engine.cu:5420-5430`）。

セットアップは run config に値を記録し、`serve.server.child_env()` が子エンジン用環境へ適用します。ここで対象環境変数の値変換はなく、`str(v)` の結果がそのまま子プロセス環境に入ります（`terminal/strata_control/setup_config.py:433-440`、`terminal/serve/server.py:4007-4028`）。

## ログと測定値

- gfx12 で Strata がこの既定値を新たに注入し、MMQ build なら stderr に `strata: gfx12 (RDNA4): a model with K-quant experts (Unsloth UD-Q4/Q5/Q6_K_XL) reads its prompt on llama.cpp's MMQ kernels ...` の行を出します。MMQ なし build では `... reads its prompt on Strata's own kernels; the 'prompt kernels' line below gives the counts` と出します（`engine/src/core/arch_defaults.cpp:373-386`）。
- CUDA は既定値を注入してもその時点では説明行を出さず、読み込んだモデルが K-quant expert を含む場合に `nv_kq_default_line()` の行を stderr に出します（`engine/src/core/nv_defaults.cpp:287-299,312-324`、`engine/src/program/generate.cpp:5412-5419`）。変数が事前設定済みならこの既定値注入起点の行は予約されません。
- `strata-q36` の環境変数設定自体にはログ出力がありません（`engine/src/qwen35/q36_engine.cu:5424-5430`）。
- gfx12 のソース文字列には R9700 / UD-Q4_K_XL の prompt 4K +10.3%、8K +14.3%、32K +16.8%、first-token KL 0.031（約 2K の prompt 24 件）との記載があります。これはソースコメントに記録された測定値であり、本調査で再測定していません（`engine/include/strata/core/gfx12_extra.hpp:22-26`）。

## 根拠

- CUDA の既定値条件と値保持: `engine/src/program/generate.cpp:4421-4488`、`engine/src/core/nv_defaults.cpp:260-273,312-325`。
- gfx12 の既定値、OS / arch / master switch 条件とログ: `engine/include/strata/core/gfx12_extra.hpp:54-68`、`engine/include/strata/core/gfx12_platform_defaults.hpp:10-16`、`engine/src/core/arch_defaults.cpp:373-386`。
- master switch の parse と cache: `engine/include/strata/core/defaults_026.hpp:21-30`。
- `strata-q36` の未設定時設定: `engine/src/qwen35/q36_engine.cu:5420-5430`。
- Unsloth run config と子プロセスへの適用: `terminal/setup.py:4741-4759`、`terminal/strata_control/setup_config.py:433-440`、`terminal/serve/server.py:4007-4028`。
