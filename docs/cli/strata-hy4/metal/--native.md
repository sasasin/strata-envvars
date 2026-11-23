# `--native`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--native` |
| 別名 | なし（`--model` も同じモデルパス変数を設定する別表記） |
| 値 | モデルファイルのパスを1つ取る |

## 役割

Metal runner に読み込ませる Strata モデルファイルを指定する。`--native` と `--model` はどちらも同じ `model` 変数に値を設定し、その値がモデルのロードと serve 設定に使われる。

## 使い方

```sh
strata-hy4-metal --native SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --load-only
```

## 値と既定値

値は `argv` の次要素を文字列として受け取り、パス形式や存在を parser 段階では検証しない。既定値は空文字列で、`--native` を指定しない場合も `--model` を指定しない場合もモデル未指定として扱われる。両方またはいずれかを複数回指定すると、走査順で最後に代入された値が残る。値のない指定に対する個別の検証はない。

## 実行時の動作

parser は `--native` の次の引数を `model` に代入する。後段では `model.empty()` を確認し、空なら usage を stderr に出して終了コード 2 で終了する。空でなければ Metal context を初期化し、`Model::load` にそのパスを渡してモデルをロードする。ロード成功後、serve モードでは同じ値を `ServeOpts::model` に設定する。

`Model::load` は指定パスを reader と `O_RDONLY` で開く。manifest がない場合、ファイルを開けない場合、mmap に失敗した場合などはロード失敗となり、呼び出し元が `load: <理由>` を stderr に出して終了コード 1 を返す。モデルを開くときは read-only mmap を使う通常経路と、Metal working set / buffer 条件などによる cold-experts 経路がある。

## 適用条件と副作用

このオプションは `strata-hy4-metal` のモデル指定に適用される。実際のモデルロードは Metal context の初期化後に行われるため、`--load-only` と併用してもモデルの読み込み処理自体は実行される。ロードでは指定ファイルを読み取り専用で開き、通常経路では read-only の private mmap を作成する。`--native` 単独によるモデルファイルへの書き込みは確認できない。

## 出力とエラー

- モデル値が未指定または空の場合、usage を stderr に出して終了コード 2。
- モデルロードが失敗した場合、`load: <理由>` を stderr に出して終了コード 1。
- モデルロード成功時は、ロード量や所要時間を含む `[load] mapped ...` 行が stderr に出る。

値なしの指定時の挙動は、parser が次の `argv` 要素を境界確認なしで読む実装から分かる範囲に限られ、安定した診断や終了コードは確認できない。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1507` — `model` の空文字列初期値と `--model` の代入。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1589-1591` — `--native` が同じ変数へ値を代入する parser 分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1606-1608` — 未知引数の stdout/stderr 出力と終了コード 2。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1626` — モデル未指定時の usage、ロード呼び出し、失敗時の出力・終了コード。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1628-1635` — ロード成功ログと `--load-only` の分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1639` — serve 設定へのモデルパスの転送。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:214-244` — reader と read-only file descriptor によるロード、manifest・open・mmap の失敗経路、cold-experts 選択。
