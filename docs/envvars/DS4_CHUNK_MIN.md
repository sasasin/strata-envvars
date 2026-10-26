# `DS4_CHUNK_MIN`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 エンジンが prompt を処理するとき、chunked prompt 経路を検討する最小 token 数を指定します。値は `chunk_min` に入り、`Model::feed()` と `Model::feed_mark()` が chunked path の前提条件として使います。設定値以上なら必ず chunked pass になるわけではなく、後段の経路選択が windows of 16 を選ぶ場合があります。

この変数を読む `ds4_model.cu` は、ビルドオプション `STRATA_BUILD_DSV41` で作られる `strata-dsv41` に含まれます。通常の `strata` 実行経路すべてに適用される設定ではありません（`CMakeLists.txt:797-811`）。

## 値と判定

値は `std::atoi()` で整数に変換し、`std::max(1, ...)` で下限を 1 にします。文字列全体の妥当性検査や上限 clamp はありません。`atoi` が初期部分から読むため、たとえば `24tail` は 24、数値に変換できない文字列や空文字は 0 となり、最終的に 1 です。先頭空白や符号も `atoi` の変換規則に従います。

| 状態 | `chunk_min` |
|---|---:|
| 未設定 | 初期値 512。ただし後述の all-flow 条件を満たすと 2 |
| 明示設定（例 `128`） | 変換した整数。ただし最低 1 |
| 空文字、数値で始まらない文字列、0、負数 | 1 |

既定値 512 は `Model::Impl` の初期値です。全 GPU の chunk が flow 対応と判定された場合、環境変数が未設定なら `kFlowChunkMin`（2）へ変更します。環境変数が空文字を含め設定済みなら、この自動変更は行いません（`ds4_model.cu:812-815, 2752-2757`）。

## 有効になる条件

- `strata-dsv41` がビルドされ、DeepSeek V4.1 の `Model` がロードされる必要があります。`STRATA_BUILD_DSV41` の既定は OFF です（`CMakeLists.txt:797-811`）。
- `chunk_min` は chunked prompt path が利用可能なときだけ意味を持ちます。`chunk` が 0 以下なら `Model::feed()` は常に windows 経路へ進みます。chunk は `prompt_par` が真であることに加え、`--prefill-chunk 0` などで 0 にされていない必要があります（`ds4_model.cu:1924-1931, 1990-1999, 9360-9367`）。
- `DS4_WINDOWS` が設定されていると、通常の単一 GPU・非 thread モードで既定の chunked prompt path を選ぶ条件が外れます。ただし `par` または tensor parallel が有効な場合、この変数だけでは `prompt_par` は無効になりません（`ds4_model.cu:1924-1931`）。
- chunk 用 buffer の確保に失敗し、実装が chunk を 0 に戻した場合も chunked path は使われません。環境変数はこの fallback を防ぎません（`ds4_model.cu:2593-2636`）。

## 実行時の詳細

環境値はモデルの `load()` 中、prompt chunk の設定時に読み取られ、その値は `Model::Impl` の `chunk_min` に保持されます。プロンプトごとに `getenv()` を再評価するコードはなく、load 後にプロセス環境を変更しても閾値には反映されません（`ds4_model.cu:1990-1999`）。

`Model::feed()` は `chunk > 0 && n >= chunk_min` のときだけ chunked path の選択に進みます。通常は `pick_path(n)` の結果により `forward_chunks()` と `feed_windows()` を選びますが、`logits_rows > kWin` の場合は `pick_path()` を介さず `forward_chunks()` を呼びます。閾値未満、または `chunk <= 0` なら `feed_windows()` です（`ds4_model.cu:9356-9367`）。`feed_mark()` も `n >= 2 && chunk > 0 && n >= chunk_min` のときだけ chunked path を検討し、その後 `pick_path(n)` が偽なら windows 経路に戻ります（`ds4_model.cu:9369-9383`）。

chunked path の通常選択に使う token 数の境界は別変数 `DS4_PICK_MIN` が決め、未設定・空文字なら既定 96 です。`DS4_PICK=adaptive` なら適応選択も加わります。このため `DS4_CHUNK_MIN` は chunked path の適用下限であり、それ単独では実際に flow を選ぶことを保証しません（`ds4_model.cu:7982-7997`, `ds4_pick_rule.hpp:18-27`）。

明示設定は `calibrate_paths()` の自動 path calibration も抑止します。未設定で既定閾値が 2 の場合でも calibration は抑止されます（`ds4_model.cu:7795-7802`）。これは prompt の経路選択を直接固定する作用とは別です。

## 根拠

- `src/dsv41/ds4_model.cu:812-815`: 512 の初期閾値と flow 用の閾値 2。
- `src/dsv41/ds4_model.cu:1924-1931, 1990-1999`: chunked path の有効化条件、`DS4_CHUNK_MIN` の読み取り、変換と下限 clamp。
- `src/dsv41/ds4_model.cu:2752-2757`: all-flow かつ環境変数未設定時の閾値変更。
- `src/dsv41/ds4_model.cu:2593-2636`: chunk buffer 確保失敗時に chunk を縮小し、最終的に windows に fallback する処理。
- `src/dsv41/ds4_model.cu:7795-7802, 9356-9383` と `src/dsv41/ds4_pick_rule.hpp:18-27`: calibration の抑止、feed 経路での閾値利用、別の flow 境界。
- `CMakeLists.txt:797-811`: DeepSeek V4.1 エンジンが別実行ファイルとして任意ビルドされる条件。

`docs/DETAILS.md` と関連するユーザー向け設計資料には、この変数を直接説明する記載を確認できませんでした。リポジトリ内のテスト用 `tools/dsv41/bytecheck.sh` は `DS4_CHUNK_MIN=100000` を windows 経路のケースで設定していますが、テストコードは挙動の根拠には用いていません。
