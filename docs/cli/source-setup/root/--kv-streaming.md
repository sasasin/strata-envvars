# `--kv-streaming`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などの wrapper 経由を含む） |
| オプション | `--kv-streaming` |
| 別名 | なし |
| 値 | `auto`、`on`、`off` |
| 既定値 | `auto` |

## 役割

長い context で KV cache を RAM に置き、attention が使う窓だけを VRAM に常駐させる設定を選びます。`setup.py` がモデル用の実行設定を作る際に判定され、engine の `--kv-resident 32768` として反映されます。この option 自体は engine の引数ではありません。

## 使い方

Linux で 128K context の KV streaming を明示して設定し、モデルを起動しない例です。

```sh
./setup.sh --setup --context 131072 --kv-streaming on --no-start
```

`setup.sh` は引数を `setup.py` に渡します。Windows では同じ値を `START-HERE.bat --setup --context 131072 --kv-streaming on --no-start` のように指定できます（[`docs/cli/README.md`](../../README.md) の `source-setup` 節）。

## 値と既定値

- `auto`（既定）: 64K 以上の context で、モデルの RAM 見積もり、KV cache の見積もり、および 1 GB の余裕を RAM が満たす場合に有効化します。
- `on`: 同じ 64K 以上の条件で RAM 判定を上書きし、有効化します。ただし RAM 不足の警告が出ます。WSL では有効化されません。
- `off`: 有効化しません。
- 値は `argparse` の `choices` により小文字の3値に限定されます。他の値は parser error となります。値の省略は `auto` と同じです。

RAM の見積もりは `context × 13 × KV_CELL_BYTES[kv] / 1e9` で、`q4_0` は 576 bytes、`k8v4` は 816 bytes、それ以外は辞書の fallback 1056 bytes を使います。コードコメントでは 12 QSA layers と draft layer 分と説明されています。

## 実行時の動作

通常の 64K 以上の context では、`off` なら KV cache を VRAM に残します。`auto` は RAM が `model["ram_gb"] + KV 見積もり + 1 GB` 以上の場合に有効化し、`on` はその RAM 判定を満たさなくても有効化します。有効時は生成する engine 引数列に `--kv-resident 32768` を加えます。context が 64K 未満なら `on` でも引数は加わりません。

有効時の KV RAM は resident budget とも関係します。対象モデルに budget があり、利用者が `--resident-budget-gib` を指定していない場合、setup は KV 分を差し引いて budget を計算します。利用者が budget を指定した場合はその値を保ち、KV cache 分が上乗せになる旨を警告することがあります。

生成した `args` はモデルの run config に保存され、run script から server/engine に渡されます。setup は設定ファイルを一時ファイルへ書いてから置換します。`--no-start` を付けなければ、設定生成後に通常の起動経路へ進みます。

## 適用条件と副作用

- 有効化の context 下限は 65536 tokens（64K）です。
- WSL は streaming 非対応として常に無効扱いです。`on` を指定しても `--kv-resident` は生成せず、`on` の指定に対して無効化理由を表示します。
- `auto` で RAM 見積もりを満たさない場合は VRAM 常駐のままとなり、必要 RAM と搭載 RAM の説明が出ます。`on` で見積もりを超えて有効化すると paging または負荷時の RAM 枯渇の可能性を警告します。
- 設定再生成により `--kv-resident` の有無が変わり得ます。setup は run config と起動用 script を生成・更新します。

## 出力とエラー

- RAM に余裕がある場合、有効化時に KV cache の RAM 見積もりと「more experts fit in VRAM」に相当する `[ok]` 行を表示します。
- WSL、RAM 不足、または 64K 未満で `on` を指定した場合は、指定が適用されない理由または RAM リスクを `[!]` warning として表示します。これらは当該分岐での warning であり、`--kv-streaming` 自体による parser error ではありません。
- 定義済み以外の値は `argparse` が拒否します。CLI の引数検証後に実行されるため、setup のモデル設定処理には進みません。

## 根拠

- 索引上の tool ID、wrapper 共有、コマンドスコープ: `docs/cli/README.md:13,1465-1495`（この文書の作成先リンクは `:1494`）。
- Parser の選択肢と既定値: `setup.py:8545-8547`。
- KV RAM 計算式と mode 判定（64K、RAM 見積もり、WSL 除外）: `setup.py:5714-5727`。
- `q4_0` / `k8v4` の KV cell サイズ: `setup.py:251`。
- WSL 判定: `setup.py:6519-6521`。
- 有効化・無効化・RAM 不足時の出力、engine 引数追加、resident budget 相互作用: `setup.py:9472-9506`。
- 設定の一時ファイル書き込みと置換: `setup.py:6154-6159`。
- run config 保存、run script 生成、起動経路: `setup.py:9712-9730,9759-9766`。
- POSIX wrapper が全引数を渡す箇所: `setup.sh:12,76`。Windows wrapper が `setup.py` に渡す箇所: `START-HERE.bat:48,53`。

調査範囲は上記 commit の `setup.py` と確認可能な wrapper / 索引です。別 platform の runtime 実測、WSL 上での実行、各 backend の性能差は調べていません。
