# `STRATA_SPEC_TRACE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

CLI の speculative generation ループで、検証ウィンドウごとの値を指定ファイルへ記録するベンチマーク・診断用フックです。生成方針やモデル計算を切り替えず、ラウンドの計測値と draft probability を後から調べるためのテキスト記録を出します。通常の逐次生成や serve のリクエスト処理にこの記録処理はありません。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | 記録しない |
| 空文字 | 記録しない |
| 空でない文字列 | その文字列をファイル名として `fopen(path, "w")` を試みる |

値の数値変換、真偽値判定、空白除去、パスの加工はありません。相対パスはプロセスの作業ディレクトリ基準です。`"w"` で開くため、同名ファイルがあれば内容を上書きします。ファイルを開けなかった場合は記録先が null のままになり、警告やエラーを出さずに通常の生成を続けます。

## 有効になる条件

- `src/program/generate.cpp` の speculative generation ループに入り、`strata::spec::spec_loop_runs(...)` が true であることが必要です。CLI の `--spec` 等で speculative ループを使わない実行では、この環境変数を読みません。
- `timed_round` は `!first_window` で決まります。native pack で最初の window を loop 内で処理する場合はその window が除外されます。通常の経路では speculative loop に入る前に最初の token を処理済みなので、loop 内の最初の window から出力対象です。いずれも正常に計測処理を完了した timed round が対象です。
- 値を読むのはループ初期化時の一度だけです。ファイルの open に失敗しても再試行せず、実行中に環境を書き換えても記録先は変わりません。

## 実行時の詳細

ファイルは speculative loop の初期化時に開かれます。各 timed round の計測後、1行に次の空白区切りフィールドを書きます。

```text
T a sfx ms p1 p2 ...
```

- `T`: 実際に verifier に渡したウィンドウ行数。suffix lookup や lookup chain、context 上限による調整後の値。
- `a`: verifier の出力と draft が一致して受理された draft 数。
- `sfx`: このウィンドウが suffix lookup 由来なら `1`、それ以外は `0`。
- `ms`: ラウンド開始から次の draft 作成までの経過時間（ミリ秒）、小数第3位まで。生成ループはこの測定値を集計にも使います。
- `p1 ...`: ラウンドの window 選択に使われた draft probability 配列 `dwin` の先頭 `o.spec - 1` 要素、小数第4位まで。ウィンドウ幅にかかわらず列数は `--spec` に基づき一定です。

最後の行には改行を付け、生成ループ終了後にファイルを閉じます。EOS を受理した round はループ内で計測・出力処理に進む前に抜けるため、その round の行は出力されません。生成途中のエラーで関数が早期 return した場合も、通常の終了時 close 処理には到達しません。

この変数自体による stdout/stderr のログや生成結果の変更はありません。ファイル出力の `fprintf` / `fclose` の戻り値も検査していないため、open 後の書き込み失敗はコード上で報告されません。

## 根拠

- `src/program/generate.cpp:16095-16103` — speculative generation ループへの条件付き進入。
- `src/program/generate.cpp:16398-16407` — ベンチ用途の説明、環境変数の読み取り、空値判定、`"w"` での open。
- `src/program/generate.cpp:16583-16586,16646-16649` — 最初の window と timed round の区別、および受理 draft 数。
- `src/program/generate.cpp:16693-16715` — EOS 判定後の計測、行の書き出し、フィールド形式と値の精度。
- `src/program/generate.cpp:16720-16726` — ループ正常終了時の commit 待ちとファイル close。

`docs/DETAILS.md` と関連資料に `STRATA_SPEC_TRACE` の追加仕様や測定結果は見つかりませんでした。上記は調査対象 commit の実装から確認できる範囲です。
