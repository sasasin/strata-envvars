# `STRATA_HIP_DYNAMIC_QUEUES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP ビルドの起動時に、Strata 独自の `STRATA_HIP_DYNAMIC_QUEUES` を `DEBUG_HIP_DYNAMIC_QUEUES` の設定判断に使います。条件を満たさない場合、Strata は HIP 初期化前に後者を `0` に設定します。`STRATA_HIP_DYNAMIC_QUEUES` が `1` で始まる場合、または `DEBUG_HIP_DYNAMIC_QUEUES` がすでに設定済みの場合は、その設定を行いません。これは HIP ランタイムへ渡す環境変数を Strata が準備する処理であり、ランタイム内部で queue がどう割り当てられるかは本調査の対象外です。実装は `main`（Windows HIP では `engine_main`）にあります（`engine/src/program/generate.cpp:3662-3666,3816-3832`）。

## 値と判定

`DEBUG_HIP_DYNAMIC_QUEUES` の有無を先に `std::getenv` で調べ、未設定の場合だけ `STRATA_HIP_DYNAMIC_QUEUES` を読みます。後者は値全体の parse ではなく、先頭バイトが文字 `'1'` かだけを判定します（`engine/src/program/generate.cpp:3821-3828`）。

| ビルド | `STRATA_HIP_DYNAMIC_QUEUES` が未設定 | 設定時に既定を保つ値 | `DEBUG_HIP_DYNAMIC_QUEUES` 未設定時に `DEBUG_HIP_DYNAMIC_QUEUES=0` を設定する値 |
|---|---|---|---|
| `STRATA_USE_HIP` かつ `!STRATA_HIP_GFX906` | `DEBUG_HIP_DYNAMIC_QUEUES=0` を設定 | 先頭が `1`。例: `1`, `10`, `1anything` | 空文字、`0`, `true`, `TRUE`, ` 1`, `-1` など先頭が `1` 以外の値 |
| それ以外（CUDA、非 HIP、`STRATA_HIP_GFX906` ビルド） | この分岐は実行されない | 該当なし | 該当なし |

比較は大文字小文字を含む文字列全体の比較でも数値変換でもありません。先頭文字だけを大文字小文字の区別ありで比較し、空白除去や数値妥当性の検査はしません。先頭が `1` 以外なら、環境変数の値が無効でも `DEBUG_HIP_DYNAMIC_QUEUES=0` を設定します。`DEBUG_HIP_DYNAMIC_QUEUES` が空文字を含め何らかの値で設定済みなら、`STRATA_HIP_DYNAMIC_QUEUES` の値にかかわらず既存値を変更しません（同 `generate.cpp:3821-3828`）。

## 有効になる条件

- コンパイル条件が `STRATA_USE_HIP` かつ `!STRATA_HIP_GFX906` であることが必要です。したがって、この処理は NVIDIA 向け CUDA ビルドでは動かず、gfx906 専用 HIP ビルドも除外されます（`engine/src/program/generate.cpp:3816-3832`）。
- 起動時の早期終了より後まで処理が進む必要があります。`--version` / `-V`、`--families`、`--geometry`、`--expert-support` の各分岐はこの処理より前にあります（`engine/src/program/generate.cpp:3696-3735,3816-3832`）。
- `DEBUG_HIP_DYNAMIC_QUEUES` が設定済みなら、それが優先されます。空文字も「設定済み」です（`engine/src/program/generate.cpp:3821-3828`）。
- この分岐に CLI 引数、モデル状態、サーバーモードによる追加条件はありません。サーバー経路についても、環境変数を独自に解釈する分岐はここにはなく、このエンジンの起動処理が実行される場合に限って適用されます（同 `generate.cpp:3662-3666,3816-3832`）。

## 実行時の詳細

エンジン起動時に一度評価し、`DEBUG_HIP_DYNAMIC_QUEUES` が未設定で対象値の先頭が `1` でなければ、Windows では `_putenv_s("DEBUG_HIP_DYNAMIC_QUEUES", "0")`、それ以外では `setenv(..., 0)` を呼びます。後者の `0` は既存値を上書きしない指定です。直後に `prime_hw_queues()` が呼ばれ、その中でデバイス数確認などの GPU runtime 呼び出しが始まります。このため、Strata はこの設定を runtime 初期化より前に準備します（`engine/src/program/generate.cpp:3816-3832,3482-3489`）。

この値を CLI 引数や設定ファイルから読む処理はありません。対象値自体はこの起動箇所でのみ読み取られ、起動後に環境を変更してもこの判定は再実行されません。Strata がこの値を子プロセスへ渡す処理も、対象名の参照箇所にはありません（同 `generate.cpp:3821-3828`）。

## ログと測定値

この分岐は対象値や設定結果を直接ログに出しません（`engine/src/program/generate.cpp:3816-3832`）。後続の `prime_hw_queues()` は、キューを開いたとき `strata generate: opened %zu GPU queues in a fixed order (STRATA_HIP_QUEUE_PRIME=0 turns it off)` を出力し、特定条件では `GPU_MAX_HW_QUEUES` を理由にキューを priming しない旨を出します。これらは queue priming の結果を示すログで、`STRATA_HIP_DYNAMIC_QUEUES` の値や効果を報告するログではありません（`engine/src/program/generate.cpp:3482-3530`）。本環境変数に対する Strata の測定値は、条件を特定できる形では確認できません。

## 根拠

- `engine/src/program/generate.cpp:3816-3832` — build 条件、環境変数の優先順位・判定・設定、および `prime_hw_queues()` の呼び出し。
- `engine/src/program/generate.cpp:3662-3666,3696-3735` — 実行入口と、その前に行われる早期終了。
- `engine/src/program/generate.cpp:3482-3530` — 後続する queue priming とそのログ。
