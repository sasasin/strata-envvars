# `STRATA_DS4_READ_PIECES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。Strata 外部ライブラリの環境変数動作は対象外です。

## 役割

`maya-ds4 --serve --parallel N`（複数会話）の要求受付中に、プロンプトを一度に読み切らず、他の要求のプロンプト読み込みや回答生成と交互に進める機能を有効にします。既定は無効です。単一会話の serve ループではこの変数を読まず、`--parallel` が複数会話でもモデルの prompt chunk が無効なら有効になりません。

## 値と判定

| 設定値 | 判定 |
|---|---|
| 未設定 | `env_count` は `0` を返し、この変数の既定値 `0` により無効 |
| 空文字 | `atoi("")` は `0` となり無効 |
| 正の整数に変換される値 | `atoi` の結果が 0 より大きければ要求を有効化。例: `1`, `2`, ` 3`, `4tail` は正数として扱われる |
| 0、負数、数値に変換できない文字列 | `atoi` の結果が正でないため無効。例: `0`, `-1`, `true`, `abc` |

実装は文字列全体の検証をせず `std::atoi` を使います。先頭の空白と符号を含む整数接頭部が変換対象で、数値の後ろの文字は判定されません。値に対する追加の上限、clamp、無効値警告はありません。読み取りは複数会話の serve 分岐で一度行い、結果をその分岐内の `const bool read_pieces` に保持します。`static` cache ではありませんが、通常この serve 分岐はプロセス内で一度だけ実行されるため、実行中の環境変更を再評価しません。

## 有効になる条件

- `--parallel N` によりモデルの会話数が 1 より大きく、serve の複数会話経路に入ること。
- `m.prompt_chunk() > 0` であること。これはモデル設定で決まります。`--prefill-chunk` とモデルの chunk 既定値が関係し、`DS4_CHUNK` が設定されると chunk 値を上書きします。単一 GPU の既定 chunk 経路にはビルド内定数 `kChunkedPromptDefault` と `DS4_WINDOWS` が関係し、Metal ビルドでは `STRATA_METAL` 条件下の `DS4_NO_CHUNKS` も prompt chunk 経路に関係します。また chunk 用 kernel が未対応のモデル状態や prompt buffer の確保失敗により chunk が 0 に戻る経路があります。
- 画像を含む `GENI` 要求は、`read_pieces` が有効でも、その要求のプロンプト全体を先に読む経路です。

この環境変数に CLI の直接上書きはありません。`--parallel` は複数会話経路を選び、`--prefill-chunk` / `DS4_CHUNK` は `m.prompt_chunk()` を通じた有効条件に影響します。値が正でも chunk が 0 の場合は無効です。

根拠: `src/dsv41/ds4_main.cpp:1355-1357,1532-1541,1853-1859`; `src/dsv41/ds4_model.cu:1085,2718-2728,2788-2805,2936-2942,3550-3562`; CLI parse は `src/dsv41/ds4_main.cpp:2549,2583-2587`。

## 実行時の詳細

複数会話経路に入ると、環境値を `env_count("STRATA_DS4_READ_PIECES", 0)` で読みます。共通 lambda は unset を 0 にし、`atoi` の結果が正の場合だけその値を返し、それ以外は呼び出し元が指定する既定値を返します（`src/dsv41/ds4_main.cpp:1532-1541`）。`read_pieces` が真なら、画像なし要求は到着時に prompt 全体を同期で読み切らず、`read_line` に登録されます。複数の読み込み要求があると各 prompt が交互に最大 `read_piece` token ずつ進み、その間に回答中の要求が `read_rounds` 回の round を行います。prompt が一つだけで回答もない場合は、次の要求行が来るまで chunk 境界で yield しながら残りをまとめて読みます（`src/dsv41/ds4_main.cpp:1779-1795,1851-1868,1886-1914`）。

piece の既定サイズは `m.prompt_chunk() * m.pipeline_stages()` token で、関連変数 `STRATA_DS4_READ_PIECE` が正数ならその倍率を掛けます。回答 round 数の既定は 1 で、別変数 `STRATA_DS4_READ_ROUNDS` の変換結果が正数ならその値が使われ、正数でなければ 1 になります（同ファイル `1538-1541`）。この変数自身は piece サイズや round 数を変更しません。

無効時または chunk がない場合、要求を受け付けた時点で prompt 全体を読みます（同ファイル `1853-1859`）。有効化専用のログはありません。serve 起動時には stderr に `maya ds4 serve: ... conversations at once (--parallel): GEN needs rid=<id>; STOP <rid>` が出ます（`1550-1551`）。prompt 読み込み中は stdout に `PP` 進捗行が出て、正常完了後は `DONE` と stderr の request timing が出ます（`1217-1221,1305-1310,1571-1582`）。STOP 中に読み込みが止まれば stderr に停止理由、stdout に cancel の `DONE` が出ます。feed 失敗時は stderr に `ds4: ...`、stdout に `ERR` と cancel の `DONE` が出ます（`1314-1340`）。環境値そのものが不正な場合に専用エラーや警告を出す処理はありません。

## 根拠

- 候補名の全参照は `rg` で確認しました。実コードでの名前の参照は `src/dsv41/ds4_main.cpp:1537` の一箇所です。コメント内の言及は同ファイル `1021,1526`、同梱 Project Maya の notice `third_party/project-maya/NOTICE.md:64` にあります。共通 lambda の他の呼び出しは別名 `STRATA_DS4_READ_PIECE` と `STRATA_DS4_READ_ROUNDS` で、候補名を動的に受け取る別の helper はありません。
- 値変換と条件: `src/dsv41/ds4_main.cpp:1532-1541`。
- turn scheduling と画像要求の例外: `src/dsv41/ds4_main.cpp:1771-1795,1843-1868,1886-1914`。
- prompt chunk の生成条件と fallback: `src/dsv41/ds4_model.cu:1085,2718-2728,2788-2805,2936-2942,3550-3562`; 公開 accessor は `src/dsv41/ds4_model.cu:14938-14944`。
- `docs/DETAILS.md` にこの変数の説明は見つかりませんでした。環境変数候補一覧 `docs/envvars/000_envvers.md` には掲載されています。
