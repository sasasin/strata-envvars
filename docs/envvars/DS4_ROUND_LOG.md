# `DS4_ROUND_LOG`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata-dsv41` の `--spec-eval` 実行で、draft の提案と検証の各 round を TSV 形式でファイルに記録します。一般の生成経路や server mode のログには使われません。`strata-dsv41` 自体は `STRATA_BUILD_DSV41` が有効なビルドでのみ作られ、この CMake option は既定で OFF です。

## 値と判定

この変数は真偽値として parse されず、`std::getenv("DS4_ROUND_LOG")` が null かどうかだけで設定有無を判定します。

| 値 | 動作 |
|---|---|
| unset | ログファイルを開かず、追加ログを出さない |
| 空文字 | 設定ありとして `fopen("", "wb")` を試す。open に失敗した場合はエラー表示なしでログ出力されない |
| 空でない文字列 | その文字列をパスとして `fopen(path, "wb")` する。開けた場合は既存ファイルを切り詰めて書き込む。`1` などの値も特別扱いしない |

ファイルを開けなかった場合に stderr への警告や別パスへの fallback はありません。パスの親ディレクトリ作成もしません。

## 有効になる条件

- `strata-dsv41` を `STRATA_BUILD_DSV41=ON` でビルドしていること（`CMakeLists.txt:798-809`）。
- `--spec-eval IDS.json` を指定し、モデルの load が成功すること。CLI は `--spec-eval` を選ぶと `spec_eval()` を呼びます（`src/dsv41/ds4_main.cpp:1293-1305`）。
- `spec_eval()` 内の `round()` が draft 経路を使い、少なくとも1 draft を残し（`keep > 0`）、`m.verify()` が成功すること。draft が残らない round、非 speculative の round、検証失敗前の時点では行を記録しません（`src/dsv41/ds4_main.cpp:172-203`）。

変数が設定されても、spec-eval が実行されない場合はファイルを開きません。`spec_eval()` の `spec` 引数が false の場合も通常 `keep` が 0 のままになり、round 行は出力されません。

## 実行時の詳細

`spec_eval()` の開始時に一度だけ変数を読み、指定パスを `wb` モードで開きます。この読み取りは `main()` がモデルをロードした後、spec-eval 経路を選択して呼び出した時点です。判定結果を static cache してはいませんが、同じ `spec_eval()` 実行中に環境変数を変更しても再読込されません。

検証に成功した speculative round ごとに、次のタブ区切りの1行を出します。

```text
segment_name<TAB>drafts_offered<TAB>accepted<TAB>confidence_1<TAB>...<TAB>confidence_N
```

`drafts_offered` は `keep`（検証に渡した draft 数）、`accepted` は verifier が受け入れた draft 数です。confidence は残した各 draft の値を小数点以下4桁で出力します。環境変数を読む直前に `g_round_tag` へ現在の segment 名を設定しており、confidence 値は `m.draft()` が返した配列から使われます。各 segment の処理後に `fflush()` するため、複数 segment の実行では segment ごとにバッファが flush されます。書き込みや flush の戻り値を検査する処理はありません。

このコードにはファイルを明示的に `fclose()` する箇所がありません。正常終了時はプロセス終了に伴う処理に委ねられます。エラーで segment ループを早期 return した場合も、明示的な close はありません。

stderr には別途 `spec-eval ...` の segment 集計行が出ますが、`DS4_ROUND_LOG` 固有の有効化ログや open 失敗ログはありません。

## 根拠

- 変数の読み取り、出力ファイルの open、segment ごとの flush: `src/dsv41/ds4_main.cpp:1132-1144,1174-1179`
- tag 設定と TSV 行の内容・出力条件: `src/dsv41/ds4_main.cpp:164-203,1141-1144`
- CLI から spec-eval への分岐: `src/dsv41/ds4_main.cpp:1266,1293-1305`
- executable の build option と既定値: `CMakeLists.txt:798-809`
