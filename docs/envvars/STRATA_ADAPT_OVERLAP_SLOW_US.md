# `STRATA_ADAPT_OVERLAP_SLOW_US`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

適応層の expert swap と次の verify window を重ねる経路で、swap copy の前に人工的な待ち時間を挿入する診断用フックです。コメントも `test hook` と呼んでいます。実際のリンク速度を変更するものではなく、コピーが遅れて layer gate が待つ状況を作るため、各 layer の swap 群の前に GPU stream 上の host callback を入れます。

この変数を読む箇所は `src/program/generate.cpp` の1箇所です。`docs/DETAILS.md` と他のソースに、この変数の説明や追加の読み取りは見つかりませんでした。

## 値と判定

値は `std::atoi` で整数に変換され、変換結果が正の場合だけ遅延を入れます。文字列全体の妥当性検査や上限 clamp はありません。

| 値 | 結果 |
|---|---|
| 未設定 | `0`。遅延なし |
| 空文字 | `atoi("")` は `0`。遅延なし |
| 正数文字列（例: `5000`） | 変換結果の値だけ microseconds 待つ |
| `0` または負数 | 遅延なし |
| 数字で始まり後ろに文字が続く値（例: `5000ms`） | `atoi` が先頭の整数を変換するため、その値だけ待つ |
| 整数として変換できない文字列 | `0` となり遅延なし |

`atoi` のため、先頭の空白や符号も標準変換規則に従い、値の全体 parse・エラー報告はしません。`int` に収まらない値の結果は保証されません。

## 有効になる条件

値が正でも、適応 overlap が実際に有効で、かつ現在処理する swap 群がある場合だけ適用されます。overlap は `STRATA_ADAPT_OVERLAP=1` で要求しますが、単一 GPU、適応 tier が稼働中であることなどの条件を満たさなければ `aov` は有効になりません。対象経路では layer split、peer device、remote expert optimization、`--adapt-async`、`--pipeline-windows`、page-locked swap source、`STRATA_DMA_BATCH`、`STRATA_ADAPT_LAG` が既定の1以外、`STRATA_ADAPT_NOWAIT` 有効、device-planned layers などが overlap を妨げます。resident RAM mode では `STRATA_ADAPT_OVERLAP_RESIDENT=1` も必要です。

従って、この変数だけを設定しても待ち時間は発生しません。overlap が無効、swap が空、またはその生成バイナリで該当する adaptive GPU 経路を使わない場合、この hook のコードには到達しません。

## 実行時の詳細

`aov` が真のとき、swap の列を layer 順に処理し、最初の swap または直前と異なる layer の最初の swap で値を一度読みます。値は関数内 `static const int` に保存されるため、プロセスが動作中に環境変数を変更しても再評価されません。初期化自体はこの条件に初めて到達した時点まで遅延します。

変換値が正なら、その layer の copy を enqueue する前に `cudaLaunchHostFunc` で host callback を `adapt_stream` に登録します。callback は `std::this_thread::sleep_for(std::chrono::microseconds(...))` を実行し、その後に同じ stream 上の swap copy が続きます。このため、待ち時間は swap を含む各 layer 群につき1回挿入されます。overlap verifier は swap のある layer についてコピー到着 gate が開くまで待つため、この遅延で待機が生じ得ます。hook 自体はログを出さず、callback 登録の戻り値もこの箇所では検査していません。

この変数はソースコメントで test hook とされますが、読み取り箇所に専用のテスト build guard はありません。そのため、当該コードを含む実行ファイルでは、上記条件を満たせば通常起動でも適用されます。

## 根拠

- `src/program/generate.cpp:8511-8519` — layer ごとの最初の swap 判定、`getenv` と `atoi`、static cache、正値時の stream callback と microsecond sleep。
- `src/program/generate.cpp:8350-8379` — overlap 要求の取得、適用条件、gate の設定。
- `src/program/generate.cpp:8546-8556` — swap copy と、layer のコピー到着を知らせる gate callback の順序。
- `src/program/generate.cpp:12003-12020` — 次の window で pending swaps を反映し、overlap gate を有効化する流れ。
