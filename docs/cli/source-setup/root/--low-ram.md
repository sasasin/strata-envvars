# `--low-ram`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などの wrapper からも引数を渡す） |
| オプション | `--low-ram` |
| 別名 | なし |
| 値 | `auto` / `on` / `off` / `resident` / `mmap` |

## 役割

モデルの expert weights を RAM に全て複製できない場合に、モデル pack の `experts.bin` から読み込む低 RAM 経路を選びます。`auto` はモデルの expert 容量と RAM の見積もりで有効化し、`on` は低 RAM 経路を強制します。`resident` と `mmap` は、GPU が保持しない expert を RAM に置くか OS のファイルキャッシュ経由で読むかも指定します。

## 使い方

```bash
# RAM に合わせて低 RAM 経路を自動選択
python3 terminal/setup.py --low-ram auto

# 通常のモデルを低 RAM 経路でセットアップ
python3 terminal/setup.py --family qwen --low-ram on

# GPU が保持しない expert を RAM に常駐させる
python3 terminal/setup.py --family qwen --low-ram resident

# GPU が保持しない expert をファイルから読む
python3 terminal/setup.py --family qwen --low-ram mmap
```

実際の入口では `setup.sh` や Windows の `START-HERE.bat` から同じ parser に引数が渡されます。`--family` と `--model` は選択例であり、必要なモデル指定は環境に合わせてください。

## 値と既定値

- 省略時は `auto`。値は parser の `choices` で限定されています。未知の値は引数解析時に拒否されます。
- `auto` は expert weights の arena と RAM に残す余裕を比較します。RAM が `arena_gb × 10^9 / 2^30 + 10 GiB` 未満なら低 RAM 経路を選びます。
- `on` は低 RAM 経路を強制します。`resident` は resident variant を要求し、`mmap` は mmap variant を要求します。
- `off` はこの低 RAM 経路を無効にします。必要 RAM を満たさない通常モデルでは paging のリスクを警告し、確認を求める経路があります。
- `auto` が低 RAM 経路を選ばない場合、expert weights は通常どおり RAM に置く構成になります。

## 実行時の動作

通常の pack では、低 RAM 経路の variant はモデル・context・KV・vision encoder が使う VRAM と RAM から決まります。`auto` と `on` は、GPU が保持しない expert の残りが RAM の headroom（10 GiB）込みで収まるなら resident、それ以外は mmap を選びます。`resident` は resident を要求し、`mmap` は mmap を強制します。resident では残りの expert を `experts.bin` から RAM に一度読み込み、mmap では OS file cache を通してモデル pack から読みます。設定生成時にそれぞれエンジン引数 `--resident-experts` / `--mmap-experts` に変換され、run config の `args` に保存されます。

低 RAM 経路が有効で、pack に `experts.bin` がまだない場合、setup は `iq_pack.py --experts-bin` を実行してモデルフォルダ内に生成します。モデルの expert arena 相当の空き容量も事前計算に含めます。既存 pack にファイルがある場合は再生成しません。

## 適用条件と副作用

- `MODELS[model].get("budget")` があるモデルでは低 RAM 判定を適用しません。`--low-ram on|resident|mmap` を指定すると適用外の警告が出て、expert の RAM 予算を使う別経路になります（`auto` と `off` はこの警告の対象外です）。
- Qwen3.6-35B-A3B と Hy4-Flash の setup 経路も `--low-ram` を使わない旨を警告します。
- 自動選択された resident variant は、選択した engine が resident 対応前なら mmap に戻し、その旨を表示します。`resident` を明示した場合、この version fallback 条件には入らず、resident 引数が渡されます。複数 GPU の resident layer split に未対応の engine では、対話時に1 GPU利用を推奨し、複数 GPU を選ぶと mmap 経路になる場合があります。
- `--low-ram off` で必要 RAM が不足する通常モデルは paging される可能性があり、遅延または起動失敗の警告・確認が出ます。`--yes` との組み合わせでは、明示的な `off` はユーザーがリスクを選択したものとして扱われます。
- Intel Arc の SYCL setup wrapper は、引数に `--low-ram` がなければ `--low-ram off` を追加します。その入口では parser の既定 `auto` ではなく `off` が有効になります。
- mmap で GPU が保持する expert の割合が小さい場合、SSD 読み込みによる大幅な低速化の警告が出ます。性能の倍率はソースから一般化できないため記載していません。

## 出力とエラー

- `choices` 外の値は `argparse` により拒否されます。
- resident/mmap の選択や低 RAM 経路の容量見積もりは setup の `[ok]` 表示で報告されます。適用外・engine fallback・SSD 読み込みの懸念は `[!]` 警告として出ます。
- `--low-ram off` で RAM 不足を受け入れない場合、確認処理から setup を停止します。別の setup 失敗は `fail()` がエラーを表示し終了コード 1 で終了します。

## 根拠

- `terminal/setup.py:11564-11568` — parser の値、既定値、説明。
- `terminal/setup.py:6997-7006`、`7057-7065` — RAM 不足の式と、budget モデルを除外する有効判定。
- `terminal/setup.py:12116-12134` — budget モデルでの適用外警告、低 RAM 判定、複数 GPU 分岐、RAM 不足時の確認。
- `terminal/setup.py:12235-12270` — resident/mmap の選択条件、複数 GPU 条件、表示と SSD 読み込み警告。
- `terminal/strata_control/setup_config.py:226-245`、`433` — engine version による resident fallback、engine 引数の選択、実行 config の `args` 格納。
- `terminal/setup.py:12340-12346`、`12469-12472` — `experts.bin` 用の容量見積もりと、pack にない場合の一度限りの生成。
- `terminal/setup.py:7240-7256` — paging リスクの確認と、明示的な `off` の扱い。
- `terminal/setup.py:9908-9910`、`10328-10330` — Qwen3.6 / Hy4-Flash 系での適用外警告。
- `engine/sycl/setup_intel.py:605-606` — Intel Arc wrapper が未指定時に `off` を補う処理。
