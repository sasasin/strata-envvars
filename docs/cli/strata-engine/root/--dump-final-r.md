# `--dump-final-r`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン引数、root scope） |
| オプション | `--dump-final-r` |
| 別名 | なし |
| 値 | 出力ファイルのパス（文字列） |

## 役割

通常のエンジン経路で、各トークン処理後の最終層残差 `R` を位置・トークン ID とともにバイナリファイルへ記録します。MTP draft head の入力を調べる用途の診断出力で、コード上のコメントでは token path のみが対象です。値は `Options::dump_final_r` に保持され、実行時に出力先を開けた場合に限り記録処理が有効になります（`engine/src/program/generate.cpp:1007-1009, 4039, 23986-23987, 24316-24320`）。

## 使い方

```sh
# トークン入力で推論し、最終層残差を /tmp/final-r.bin に記録する
strata --model model.gguf --tokens 1,2,3 --dump-final-r /tmp/final-r.bin
```

既存ファイルは `"wb"` で開く際に切り詰められます。同じ出力先を使う場合は必要なデータを退避してください（`engine/src/program/generate.cpp:23986`）。

## 値と既定値

- 値を1つ取ります。パス文字列自体の形式・存在確認・書き込み可能性の事前 validation はありません。
- 未指定時の値は空文字列で、ファイルを開かず出力もしません。明示的な空文字列も同様です（`engine/src/program/generate.cpp:1009, 23986`）。
- 値を省略すると `--dump-final-r needs a value` を標準エラーへ出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3845-3848` の `next` lambda と `4039`）。
- 複数回指定した場合は parser が同じ文字列を順に代入するため、最後の値が使われます（`engine/src/program/generate.cpp:4039`）。

## 実行時の動作

実行開始後、`dump_final_r` が空でなければ `std::fopen(path, "wb")` で出力ファイルを開きます。開けた場合は `g.hc * g.n_embd` 個の `float` 用バッファを用意し、トークン処理後に `ss.R` をホストへコピーして、`int64_t` 2個のレコード `{pos, tok}`、続けて残差ベクトルの `float` 配列を書き込みます。したがってレコードはヘッダーなしの連続したバイナリで、各レコードの残差要素数はモデル実行時の `g.hc * g.n_embd` です（`engine/src/program/generate.cpp:23986-23987, 24316-24320`）。

SYCL 実装にも同じ parser とファイル形式の書き込みがあります。SYCL ではコピーに SYCL queue を使い、完了を待ってから書き込みます（`engine/sycl/src/program/generate.cpp:2035, 13308-13309, 13524-13531`）。

## 適用条件と副作用

- 通常の `engine/src/program/generate.cpp` 経路と SYCL の `engine/sycl/src/program/generate.cpp` 経路に実装されています。
- `engine/src/program/generate.cpp` は Qwen3.6-35B-A3B のモデルを検出すると、引数解析前に Qwen35 専用実装へ引き渡します（`engine/src/program/generate.cpp:3804-3818`）。専用実装にはこのオプション文字列の parser 定義が見当たらず、Qwen35 経路での利用は確認できません。
- ファイルは `"wb"` で作成・切り詰めされます。`fopen` の失敗は明示的に報告されず、戻り値が null の場合はバッファが空になり、記録処理を通りません（`engine/src/program/generate.cpp:23986-23987, 24316`）。
- `fwrite` の戻り値も確認していません（`engine/src/program/generate.cpp:24318-24320`）。書き込み先が途中で失敗した場合の通知・終了動作はこの箇所から確認できません。
- 整数・浮動小数点データはネイティブ表現のまま書かれ、ファイル内に次元や型を示すメタデータを付加する処理はありません（`engine/src/program/generate.cpp:24318-24320`）。異なる実行環境間での読み取り互換性はソースから確認できません。

## 出力とエラー

通常経路では、ファイルのオープン失敗や `fwrite` 失敗を出力する処理は見当たりません。指定値が欠ける場合は上記の parser エラーで終了コード `2` になります。未対応の引数は `unknown argument` と usage を標準エラーへ出し、終了コード `2` で返す経路があります（`engine/src/program/generate.cpp:4269-4274`）。

## 根拠

- `engine/src/program/generate.cpp:1007-1009` — オプション値の格納先とコメント上の目的・token path 条件。
- `engine/src/program/generate.cpp:3845-3848, 4039` — 値取得時の不足エラーと parser 登録。
- `engine/src/program/generate.cpp:23986-23987, 24316-24320` — ファイルを開く方法、残差コピー、バイナリレコード書き込み。
- `engine/src/program/generate.cpp:3804-3818` — Qwen35 専用経路への振り分け。
- `engine/src/program/generate.cpp:4269-4274` — 未知引数のエラー経路。
- `engine/sycl/src/program/generate.cpp:2035, 13308-13309, 13524-13531` — SYCL parser と対応するファイル出力。
