# `strata --dump-routing`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--dump-routing` |
| 別名 | なし |
| 値 | 出力先ファイルのパスを1つ取る。文字列として保持され、数値・拡張子の検証はない |

## 役割

推論中に各層・各位置で選ばれた expert ID と routing weight をバイナリ trace に記録する。代表的な用途は、実際の prompt を一度実行して routing 履歴を採取し、expert cache 用 profile の作成や cache policy のオフライン分析に渡すこと。`--serve` 経路でも trace を出力できるが、検証用の1回実行では単一プロンプトの履歴を取り出しやすい。

## 使い方

```sh
# モデルパックと token input を指定し、routing trace を新規作成する
strata --pack /path/to/model.pack --tokens '1,2,3' --dump-routing /tmp/routing.trace
```

この CLI の usage は `--dump-routing PATH` と案内している。`--tokens` など推論入力の指定が別途必要であり、このオプション自体は実行対象の prompt を選ばない（`engine/src/program/generate.cpp:1283-1289, 3851-3853`）。

## 値と既定値

- `PATH` は必須の1引数。末尾に値がない場合は `--dump-routing needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:3844-3847, 3898`）。
- 未指定時は空文字列のままで、trace ファイルを開かず記録もしない。パスの形式や書き込み先の事前 validation はない（`engine/src/program/generate.cpp:844, 10465-10477`）。
- 同じ指定を複数回行う場合、parser は後の値で `o.dump_routing` を置き換える。重複指定を拒否する処理はない（`engine/src/program/generate.cpp:3894-3899`）。

## 実行時の動作

値が空でなければ推論開始時に `fopen(PATH, "wb")` でファイルを開き、expert pool の dispatch で得た routing を書き込む。通常の pool dispatch では1レコードを `int32 layer, int32 k, k 個の int32 expert ID, k 個の float weight` の順に記録する。したがってレコード長は `8 + 8*k` bytes で、層番号は0始まり。これはヘッダーのない逐次レコードである（`engine/src/program/generate.cpp:1601-1626`）。

`--serve` の複数 token dispatch 経路では、レコード形式は同じだが routing weight を dispatch 側から取得できないため、各 weight に0を書き込む。単一 token の pool dispatch では実際の weight が記録される（`engine/src/program/generate.cpp:1631-1638, 1657-1668`）。`engine/sycl/src/program/generate.cpp` にも同名 parser と同じレコード書き込み経路がある（`1085-1134`）。

## 適用条件と副作用

- `--no-pool` と同時に指定すると、expert pool を必要とする旨を stderr に出し、終了コード 2 で拒否する。routing ID が pool が読む doorbell 経由で host に届くためである（`engine/src/program/generate.cpp:10465-10480`）。
- ファイルは `wb` で開くため、既存ファイルがあれば切り詰め、新規作成も行う。パスに書き込めない場合は `cannot write PATH` を stderr に出して終了コード 1（`engine/src/program/generate.cpp:10472-10477`）。
- server dispatch の routing trace は各 request 境界で `fflush` され、途中終了時にもそこまでのデータを残す意図が実装されている（`engine/src/program/generate.cpp:23753`）。
- 通常完了時にファイルを閉じ、stdout に `routing dumped` とパスおよび dispatch 数を表示する。`fwrite` / `fflush` / `fclose` の戻り値をこの処理で検査していないため、open 後の書き込み失敗を確実にエラーとして検出する保証はソース上確認できない（`engine/src/program/generate.cpp:1623-1626, 25395-25400`）。

## 出力とエラー

出力ファイルはヘッダーなしのバイナリ trace。対象コードはホストの `int32_t` と `float` をそのまま書き込むため、明示的な byte order 変換はない（`engine/src/program/generate.cpp:1623-1626`）。一部の Strata 補助ツールはこの record layout を読んでいる（`terminal/tools/make_profile.py:46-49, 54-63`）。

pool dispatch が compiled geometry の範囲外の層番号を検出すると stderr に `the routing trace saw layer ... outside 0..47` を出し、その dispatch の trace 書き込みを飛ばす。ここで明示的な終了処理は行われない（`engine/src/program/generate.cpp:1611-1626`）。

## 根拠

- `engine/src/program/generate.cpp:1283-1289` — usage 上の形式と隣接する診断オプション。
- `engine/src/program/generate.cpp:3844-3847, 3894-3899` — 値取得、欠落時の終了、parser 代入。
- `engine/src/program/generate.cpp:1601-1626, 1631-1668` — pool dispatch ごとの record serialization と server 複数 token 経路の weight。
- `engine/src/program/generate.cpp:10465-10480, 23753, 25395-25400` — `--no-pool` 条件、ファイル open、server flush、完了時の close と表示。
- `engine/sycl/src/program/generate.cpp:1933-1940, 5919-5936, 1085-1134, 14373-14378` — SYCL 側の parser、open 条件、record serialization、完了処理。
- `terminal/tools/make_profile.py:46-63` — Strata 補助ツール側の trace layout 読み取り。エンジンの動作根拠ではなく、利用先の照合。
