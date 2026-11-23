# `--draft`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| オプション | `--draft` |
| 別名 | なし |
| 値 | 文字列。usage が示す値は `auto`、`dspark`、`off` |

## 役割

Metal 版 Inkling runner で DSpark speculative drafting を有効にするか、実験的な draft/tree decode を選ぶ値です。既定値は `auto` で、`off` 以外の値は DSpark を有効にする要求として runner 初期化へ渡されます。`--spec-check` と `--bench` の decode では値に応じて speculative decode が使われます。これは通常の対話生成オプションではなく、この実行ファイルの検査・ベンチマーク経路に作用します。parser の usage は `auto|dspark|off` と記しますが、実装は値を列挙検証せず、追加で `tree` / `beam` / `tree6` などを特別扱いします（`engine/src/inkling2/metal/ink_metal_main.cpp:419-429, 453-457, 489-493, 550-558`）。

## 使い方

```sh
# 既定の auto で Metal 版 runner の speculative parity を調べる
strata-inkling-metal --model model.strata --spec-check

# ベンチマークで DSpark draft を明示する
strata-inkling-metal --model model.strata --bench --draft dspark

# draft を無効にして runner を初期化し、通常 decode と比較する
strata-inkling-metal --model model.strata --spec-check --draft off
```

## 値と既定値

- `--draft` を省略すると `auto` です。引数なしでは `model_path` が空として扱われ、usage を stderr に表示して終了コード 2 になります（`engine/src/inkling2/metal/ink_metal_main.cpp:419, 470-473`）。
- `off` だけが draft 無効扱いです。値は大文字小文字を含め文字列比較されるため、たとえば `OFF` は無効値として拒否されず、`off` 以外として処理されます（`engine/src/inkling2/metal/ink_metal_main.cpp:453, 489`）。
- `auto` / `dspark` の違いを分ける処理は見つかりません。どちらも DSpark を要求します。`tree` と `beam` は動的 tree budget、`tree6`、`tree8`、`tree10`、`tree12`、`tree16`、`tree24`、`tree32` は指定 budget の tree decode に使われます（`engine/src/inkling2/metal/ink_metal_main.cpp:550-558`）。
- それ以外の任意の値も parser は拒否しません。`off` 以外で DSpark を要求し、上記の tree 値に一致しなければ通常の block-8 draft 経路になります（`engine/src/inkling2/metal/ink_metal_main.cpp:453, 489-493, 550-558`）。
- 複数回指定した場合は、引数走査のたびに `draft_mode` が代入されるため最後の値が残ります（`engine/src/inkling2/metal/ink_metal_main.cpp:432-467`）。`--draft` の値を省略すると `nxt()` が不足値を stderr に出し、終了コード 2 で終了します（同 `:434-436`）。

## 実行時の動作

`off` の場合、runner 初期化へ `enable_dspark=false` を渡します。それ以外では true を渡しますが、実際に利用可能となる条件はモデル manifest に DSpark があることも含み、runner は `enable_dspark && m.man.c.has_dspark` で `use_dspark` を決めます。モデルに DSpark がなければ false となり、初期化時の runner ready 診断にも `dspark=0` と出ます（`engine/src/inkling2/metal/ink_metal_main.cpp:489-493`; `engine/src/inkling2/metal/ink_metal_runner.h:230-242, 758-764`）。

`--spec-check` は同じ prompt に通常 decode と speculative decode を実行し、生成 token の一致数・速度・accept 数を stdout に出します（`engine/src/inkling2/metal/ink_metal_main.cpp:560-585`）。`--bench` では `draft_mode != "off" && runner.use_dspark` の場合に speculative decode を選び、無効時は通常 decode として計測します（同 `:589-603`）。speculative decode は DSpark が無効、文脈上限付近、または生成上限に達した場合、通常の 1 token forward に戻ります。DSpark 有効時は draft を提案し、target の greedy token と一致する prefix のみ採用します（同 `:174-188, 297-355`）。

`selfcheck` / `--dump-logits` の経路では、DSpark が有効なら prompt forward 時に taps を捕捉します（`engine/src/inkling2/metal/ink_metal_main.cpp:517-531`）。ただし `--draft` が直接 logits を変更する処理ではなく、DSpark がある場合に補助的な tap capture を行う設定です。

## 適用条件と副作用

- 適用先は `strata-inkling-metal` の parser です。CUDA/HIP 版の同名オプションとは別 scope で、Metal 実装の値規則を記載しています（`docs/cli/README.md` の `strata-inkling-metal` 節、`engine/src/inkling2/metal/ink_metal_main.cpp:417-467`）。
- `--draft` の値検証や明示的な拒否処理はありません。未対応の値を typo として止めず、`off` 以外なら DSpark 要求として扱うため、意図と違う decode mode になる可能性があります（`engine/src/inkling2/metal/ink_metal_main.cpp:453, 489-493, 550-558`）。
- DSpark を要求すると runner はモデルに DSpark がある場合に DSpark 用リソースを準備し、メモリ確保・shader/pipeline 利用などを含む Metal runner 初期化を実行します。具体的なメモリ量や性能差はモデル・デバイス依存で、この調査では実行測定していません（`engine/src/inkling2/metal/ink_metal_runner.h:230-242, 521-524, 758-765`）。
- runner 初期化失敗は `[ERROR] runner init: ...` を stderr に出して終了コード 1 です。モデル読込失敗も stderr の `[ERROR] load: ...` と終了コード 1 です（`engine/src/inkling2/metal/ink_metal_main.cpp:481-493`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:419-429` — 既定値 `auto` と mode 関連状態。
- `engine/src/inkling2/metal/ink_metal_main.cpp:432-467` — parser、値欠落時と未知オプション時のエラー、代入方法。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-493` — model 必須条件、`off` 判定と runner 初期化・失敗経路。
- `engine/src/inkling2/metal/ink_metal_main.cpp:550-558` — tree mode の追加値と budget 対応。
- `engine/src/inkling2/metal/ink_metal_main.cpp:560-603` — `--spec-check` / `--bench` での decode 選択と出力。
- `engine/src/inkling2/metal/ink_metal_main.cpp:174-188, 297-355` — speculative decode の通常 decode fallback、draft の照合・採用。
- `engine/src/inkling2/metal/ink_metal_runner.h:230-242, 758-765` — モデルの DSpark 有無を含めた実効化と runner 診断。
