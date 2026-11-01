# `STRATA_GRP_REPS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`gr_parity` の二群 QFUSE parity チェックで、各 token 数に対して異なる乱数入力で反復する回数を指定します。Strata の通常の推論・サーバー設定ではなく、GPU カーネル検査用のテスト実行ファイルだけが読む値です。CMake は `gr_parity` 実行ファイルと `gr_parity --selftest` の CTest を登録しています（`CMakeLists.txt:1384-1387`）。

この値は二群チェックの回数だけを変え、比較方法や許容誤差は変えません。チェック対象は `T = 2..8` のグループ窓で、各反復は group-relative direct、window-indexed direct、group-relative graph replay のいずれかを順に行います（`src/kernels/gr_parity.cpp:464-470,489-490,519-530`）。

## 値と判定

| 環境変数の状態・値 | `REPS` | 動作 |
|---|---:|---|
| 未設定 | 200 | 各 `T` で200反復 |
| 空文字 | 1 | `atoi("")` が0となり、最低値1に丸める |
| 数値として0、負数、または数値変換できない文字列 | 1 | `std::atoi` の結果に `std::max(1, ...)` を適用 |
| 1以上の整数として読める値 | その整数 | 各 `T` で指定回数反復 |
| 数字の後ろに文字が続く値 | 数字部分の変換結果（最低1） | `atoi` は文字列全体の妥当性を検査しない。例: `12tail` は12として扱われる |

コードは `getenv` で設定有無を判定し、設定されていれば `atoi` で変換してから1未満を1にします。上限 clamp やエラー出力はありません。`atoi` が表現できない範囲の数値に対する扱いも、このコードでは検証していません。値はチェック開始時にローカル定数 `REPS` として読み込まれ、反復中には再読込しません（`src/kernels/gr_parity.cpp:470-474`）。CLI 引数による上書きはなく、受け付ける引数は `--selftest` のみです（`src/kernels/gr_parity.cpp:618-622`）。

## 有効になる条件

- `gr_parity` GPU テストがビルドされ実行される必要があります。これは製品の `strata` CLI やサーバー起動時には読み取られません（`CMakeLists.txt:1384-1387`）。
- 対象チェックは `STRATA_GR_V3` が偽のときだけ実行されます。`gr_parity` は起動時に `STRATA_GR_V3` が未設定なら文字列 `0` を設定し、その後チェック内で `atoi` が0以外かを判定します。そのため既定では対象チェックが走りますが、外部から `STRATA_GR_V3` に `1` などの非0値を渡すと `STRATA_GRP_REPS` の値は使われず、二群チェックはスキップされます（`src/kernels/gr_parity.cpp:340-342,611-617,470`）。
- `STRATA_GRP_KEEP_GOING` が存在する場合（空文字を含む）、二群チェックで失敗が出た後も反復を続けます。未設定なら最初の失敗後に残りの反復・後続の `T` を止めます。これは設定値の内容ではなく `getenv(...) != nullptr` で判定します（`src/kernels/gr_parity.cpp:472-473,489,509`）。

## 実行時の詳細

反復ごとに新しい乱数入力を作り、二群の量子化結果、カウンターのリセット、グループ外への書き込みがないことを参照結果と比較します。`REPS` 回を `T=2..8` の各値で行い、完走時のログには実行回数と「`%d random inputs each T`」として設定反復数が出ます（`src/kernels/gr_parity.cpp:509-530,531-588`）。したがって、失敗がなく `STRATA_GRP_KEEP_GOING` の条件にも妨げられない場合、二群チェックの run 数は `7 * REPS` です。

比較不一致や範囲外書き込みなどは `QFUSE two groups...` の診断を stdout に出し、最終的に `QFUSE` チェックを `FAIL` と表示します。失敗数は全体の `bad` に加算され、テスト末尾で `gr_read/gr_write: N failures` を出して終了コード1になります。失敗がなければ終了コード0で、`--selftest` を指定した場合はさらに `gr_parity OK` と表示します。CUDA API エラーは `check()` が stderr にエラー内容を出して直ちに終了コード1にします（`src/kernels/gr_parity.cpp:39-43,587-589,955-959`）。

## 根拠

- 直接の唯一の読み取りと値変換、関連する `STRATA_GRP_KEEP_GOING` 判定: `src/kernels/gr_parity.cpp:470-474`。
- 対象の二群反復、停止条件、各反復の比較・ログ: `src/kernels/gr_parity.cpp:489-589`。
- `STRATA_GR_V3` の cache と起動時既定値設定: `src/kernels/gr_parity.cpp:340-342,611-617`。
- テスト実行ファイルと CTest 登録: `CMakeLists.txt:1384-1387`。
