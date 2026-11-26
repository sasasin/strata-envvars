# `strata --eos-ids`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` を含む root scope） |
| オプション | `--eos-ids` |
| 別名 | なし |
| 値 | 1 個以上のトークン ID。カンマまたは空白区切りの整数リスト。各値は `0`〜`2147483647` |

## 役割

生成を終了する EOS（end-of-sequence / end-of-turn）トークン ID の集合を指定します。このオプションを指定すると EOS 停止も有効になり、生成トークンがリスト内の ID に一致した時点でデコードを終了します。省略時の ID 集合は `{248044, 248046}` ですが、通常の非 server 実行では停止自体は無効です（`engine/src/program/generate.cpp:1066-1068`）。

## 使い方

```sh
# トークン 2 または 3 を EOS として扱う（トークン入力例は別途指定）
strata --tokens '1, 42' --eos-ids '2,3'
```

## 値と既定値

- 値はカンマ、スペース、タブ、改行などで区切った整数です。`2,3` と `2 3` のどちらも受理され、区切りが連続していても読み飛ばされます。空リストは受理されません（`engine/src/program/generate.cpp:1554-1581`）。
- 各 ID は `int32` として解析され、`0` 未満、`2147483647` より大きい値、小数や整数以外の文字を含む要素は拒否されます。モデルの語彙にその ID が存在するかどうかは、この parser では検証しません（同 `:1571-1577`）。
- 指定しない場合のリストは `248044,248046` です。明示したリストはこの既定リストを置き換えます（同 `:1068`, `:4197-4200`）。
- 複数回指定した場合、各指定がリスト全体を置き換えるため、最後の有効な指定が残ります（同 `:1555`, `:4197-4200`）。

## 実行時の動作

parser は値を `eos_ids` に読み込み、成功時に `stop_eos` を有効にします（`engine/src/program/generate.cpp:4197-4200`）。通常の生成ループは prompt 部分を過ぎてから、生成候補を `produced` に追加し、リストとの一致を調べて一致時に停止します（同 `:24444-24447`）。投機的デコードでも EOS ID を確認し、EOS を含む候補以降を出さずに終了します（同 `:25205-25216`）。

EOS と判定された ID 自体は生成済み列に含まれ、最後の `output` 行にも出力されます（同 `:25403-25408`）。したがって、この指定は EOS トークンを出力から削除する設定ではありません。

関連する `--stop-eos` は EOS 停止を有効にしますが、既定の ID 集合を使います。`--eos-ids` はリストを置き換えたうえで停止を有効にするため、標準 ID と追加 ID の両方で停止したい場合は両方を列挙してください（同 `:4063`, `:4197-4200`）。`--serve` で prompt token 入力を省略する経路も停止を有効にします（同 `:4996-5001`）。

## 適用条件と副作用

この設定はエンジンの root 引数として受理され、CUDA/HIP 側の `engine/src/program/generate.cpp` と SYCL 側の `engine/sycl/src/program/generate.cpp` に同じ parser、既定 ID、停止判定があります（後者 `:703-705`, `:2161-2165`, `:13697-13700`, `:14201-14213`）。外部ファイルの読み書きやプロセス起動は行わず、生成終了条件を変更します。

## 出力とエラー

- 引数値がない場合は `--eos-ids needs a value` を stderr に出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- 空リストは `--eos-ids: token list was empty`、範囲外・不正な要素は `--eos-ids: invalid token id: expected an integer in [0, 2147483647]` を stderr に出し、parser は終了コード `2` を返します（同 `:1573-1580`, `:4197-4200`）。

## 根拠

- `engine/src/program/generate.cpp:1066-1068` — EOS 停止フラグの初期値と既定 ID。
- `engine/src/program/generate.cpp:1554-1581` — 整数リストの区切り、検証範囲、空値エラー。
- `engine/src/program/generate.cpp:4197-4200` — `--eos-ids` の parser と停止フラグ設定。
- `engine/src/program/generate.cpp:4063` — `--stop-eos` の独立した parser。
- `engine/src/program/generate.cpp:24444-24447`, `25205-25216` — 通常生成と投機的生成の停止判定。
- `engine/src/program/generate.cpp:25403-25408` — 生成列（EOS ID を含む）の出力。
- `engine/sycl/src/program/generate.cpp:703-705`, `2161-2165`, `13697-13700`, `14201-14213` — SYCL 実装における既定値、parser、停止判定。
