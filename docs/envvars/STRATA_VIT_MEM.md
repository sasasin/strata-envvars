# `STRATA_VIT_MEM`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Metal 版の独自 Vision tower reader が、ロード中および画像処理中のプロセスの `phys_footprint` を stderr に記録する診断スイッチ。重みや計算カーネルの選択・画像出力を設定する変数ではない。読み取り箇所は `tools/vision/own/vit_metal.mm` に限られる（同ファイル:73-80, 199-204, 395-402）。

## 値と判定

値の内容は parse せず、`std::getenv(...) != nullptr` で環境変数の存在だけを見る。未設定なら無効、設定されていれば値が空文字でも有効。`1`、`0`、`true`、`false`、`0anything` はすべて同じく有効で、大文字小文字・空白・数値としての妥当性は検査しない（`tools/vision/own/vit_metal.mm:73-80, 199-204, 395-402`）。

| ビルド・実行経路 | unset | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| `vit_metal.mm` を含む Metal 版 own tower を GPU で使用 | footprint 記録をしない | 空文字を含む任意の値 | なし（存在判定のみ） |
| CPU / CUDA / HIP / SYCL 版、または mtmd reader | この変数の読み取り箇所なし | 適用されない | 適用されない |

## 有効になる条件

- `tools/vision/own/CMakeLists.txt` で Apple 上に `STRATA_VIT_OWN_METAL` または `STRATA_VISION_METAL` が選ばれ、`vit_metal.mm` が own tower に組み込まれている必要がある（同ファイル:56-68, 157-163）。
- own tower の GPU 経路で `VitGpu::load` / `VitGpu::encode` が実行される必要がある。reader は `--tower own` または `STRATA_VISION_TOWER` / `--tower` の解決で own が選ばれたうえで、GPU 実行なら `--gpu` が必要（`tools/vision/strata_vision.cpp:94-112, 137-170`; `tools/vision/own/own_reader.cpp:114-125, 143-149`）。
- 変数自身を無効化・上書きする CLI 引数や他の環境変数はない。`--gpu` なしの CPU own reader、CUDA/HIP/SYCL 実装、mtmd reader では、この名前を読むコードがない。

## 実行時の詳細

ロード開始、Metal device/queue 作成後、通常 kernel のコンパイル後、重みアップロード後、work buffer 作成後、および成功した各画像処理後に `footprint_note` が呼ばれる。そこで `task_info(mach_task_self(), TASK_VM_INFO, ...)` が成功した場合、`vi.phys_footprint / 1048576.0` を MiB に換算して出力する（`tools/vision/own/vit_metal.mm:74-80, 368-379, 390-394, 430-434, 472-478, 605-613`）。

通常の dispatch では、カーネル名ごとの初回 dispatch 後に command buffer の完了を待ってから同じ footprint を記録する。既に見たカーネル名は `seen` により再記録しない（`tools/vision/own/vit_metal.mm:183-204, 206-206`）。さらにロード時には小さい `vk_add_bias` dispatch を一度実行して完了を待ち、その直後にも記録する（同ファイル:395-402）。`footprint_note` と dispatch の判定値は関数内 `static` にキャッシュされ、ロード時の小 dispatch の分岐はその場で環境を読み取る。プロセス実行中に環境を変更した場合の反映はコードで定められていない。

この診断は footprint の観測と待機を追加するだけで、画像結果の値や kernel 選択規則を変更しない。Metal GPU がない場合や kernel compile / tower load が失敗した場合はその後の観測点に到達しない（同ファイル:373-392; `tools/vision/own/own_reader.cpp:117-125`）。

## ログと測定値

成功時の stderr 形式は `vit-mem: %-34s footprint %.1f MiB\n`。ラベルは `start of the load`、`device and queue`、`plain kernels compiled`、`after one tiny vk_add_bias`、`first run of <kernel>`、`kernels compiled, self-test done`、`weights uploaded`、`work buffers`、`after a picture`。`task_info` が `KERN_SUCCESS` 以外ならこの関数からはログを出さない（`tools/vision/own/vit_metal.mm:77-80`）。この変数についてソースコードから確認できる性能測定値はない。

## 根拠

- 全読み取り箇所と存在判定: `tools/vision/own/vit_metal.mm:73-80, 199-204, 395-402`。
- Metal build 条件: `tools/vision/own/CMakeLists.txt:56-68, 157-163`。
- own GPU reader の起動・ロード・encode 経路: `tools/vision/strata_vision.cpp:94-112, 137-170`; `tools/vision/own/own_reader.cpp:114-125, 143-149`。
