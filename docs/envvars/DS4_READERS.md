# `DS4_READERS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DS4（DeepSeek V4.1）エンジンで、専門家重みをモデルファイルから読むときに使う reader の並列度を指定します。読み取り対象を pinned staging buffer に並列で読む `Pool` と、flow 経路のファイル I/O を処理する `IoQueue` の両方に値が渡されます。これは DS4 エンジン内部の実装であり、汎用 Strata エンジン全体の reader 数を設定するものではありません。

## 値と判定

DS4 のロード時に `std::getenv("DS4_READERS")` を一度呼び、未設定なら 8、設定されていれば `std::atoi` の結果を使います。その後 `std::max(1, ...)` で下限 1 にします。文字列全体の検証や上限 clamp はありません。

| 環境値 | `n_readers` |
|---|---:|
| unset | 8 |
| 空文字、数値に変換できない文字列 | 1（`atoi` が 0 を返すため） |
| `0` または負数 | 1 |
| 正の整数 | `atoi` が先頭から変換した整数 |

`atoi` のため、先頭空白や符号は整数変換に従い、数値の後ろにある非数値文字は変換結果に含まれません（例: `4tail` は 4）。整数として表現できない値の動作はこの実装で定義・検査されていません。

## 有効になる条件

この値を読む初期化ブロックは `chunk > 0` の場合に限られ、さらに `file_experts` の場合にだけ reader pool と I/O queue を作ります。`file_experts` は GGUF で常に有効になり、非 GGUF の pack では `--mmap-experts` の指定または自動判定で決まります。したがって、chunk を使わない実行経路や、chunk を使っても専門家をファイルから読まない経路では、この設定は読み取り・適用されません。

デバイスごとに `Chunk` が存在し、ring buffer がある場合に pool と queue を初期化します。flow はさらにデバイス上の層の形式などの条件を満たすと有効になり、`DS4_FLOW` や `DS4_FLOW_TP` も flow の有効性に関わります。flow が無効でも、通常の chunked prompt 経路では staging buffer へのファイル読み込みに reader pool が使われます。

## 実行時の詳細

ロード時に決めた `n_readers` は、デバイスごとの各 `Chunk` について次のように使用されます。

- `Pool(n_readers - 1, ...)` は専用 worker thread を `n_readers - 1` 本作ります。`Pool::run` の呼び出し元も仕事を処理するため、staging buffer へのバッチ読み込みに参加する実行主体は最大 `n_readers` 個です。各仕事は専門家の重みを `read_mx` または `pk.read_at` で読みます。バッチの読み込みに失敗すると `reading layer ...` のエラーを設定して処理を失敗させます。
- `IoQueue(n_readers)` は `n_readers` 本の専用 thread を作ります。flow 経路の read/copy job を処理し、読み込み完了数を更新します。flow 側は job の完了を待ってから staging から GPU ring への転送を進め、読み込み失敗を検出した場合は層・expert を示すエラーにします。

値は `load()` の初期化中に通常のローカル変数として読み、static cache には保存しません。したがって、ロード後にプロセス環境を変更しても既に作られた pool の thread 数は変わらず、次のモデルロード時に改めて読み取られます。環境変数値に応じた専用ログは確認できません。

## 根拠

- `src/dsv41/ds4_model.cu:1860-1863` — DS4 のモデルロード処理。
- `src/dsv41/ds4_model.cu:2685-2737` — chunked/file experts 条件、既定値 8、下限 clamp、各 `Chunk` の `Pool` / `IoQueue` 初期化。
- `src/dsv41/ds4_model.cu:3198-3234` — batch の専門家ファイル読み込みを reader pool で並列化し、エラーを返す経路。
- `src/dsv41/ds4_model.cu:3470-3495,3506-3512,3550-3565` — flow の I/O job 登録、完了待ち、読み込みエラー処理。
- `src/dsv41/ds4_pool.hpp:35-56,60-80` — `Pool` の専用 worker 数と呼び出し元を含む実行方法。
- `src/dsv41/ds4_pool.hpp:132-159,180-235` — `IoQueue` が指定数の専用 thread を作り、job を処理する実装。
- `docs/DETAILS.md` に `DS4_READERS` の個別設定説明や測定値は見つかりませんでした。
