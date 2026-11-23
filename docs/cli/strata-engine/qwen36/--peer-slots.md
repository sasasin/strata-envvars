# `--peer-slots`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 family の parser。単独実行時は `strata-q36`） |
| オプション | `--peer-slots` |
| 別名 | なし |
| 値 | 整数 `N`。正の値は peer GPU に置く expert slot 数の上限。0 以下は上限なし |

## 役割

Qwen3.6 の routed expert を2枚目の CUDA GPU に配置するとき、各層あたりの slot 数に上限を設けます。`--peer-device` で peer GPU を有効にした hybrid 配置で使われ、カード0の slot の後に peer GPU、残りは CPU pool へ割り当てられます。実際の slot 数は空き VRAM とモデルの expert 数でも制限されるため、この値は上限であり確保数の指定ではありません。

## 使い方

```sh
# Qwen3.6 を読み込み、CUDA device 1 に層あたり最大4 slotを割り当てる
strata --model /models/qwen36.gguf --peer-device 1 --peer-slots 4 --tokens 1,2,3
```

`--peer-device` を指定しない場合、この設定値だけでは peer tier は有効になりません。

## 値と既定値

- 値は `std::atoi` で整数に変換されます。省略時は `0` です。明示的な `0` と負数も上限なしとして扱われます。正数の場合、VRAM から算出した slot 数をその値以下に抑えます。
- 数値形式や範囲の専用 validation はありません。`atoi` が数値として読めない文字列を変換した結果は0となり、上限なし相当になります。繰り返し指定した場合は parser が順に代入するため最後の値が残ります。
- 値を必要とするオプションの直後に引数がない場合、parser は stderr に `strata-q36: --peer-slots needs a value` を出して終了コード2で終了します。

## 実行時の動作

parser は値を `peer_slots` に保存し、`Engine` に渡します。peer tier 初期化時には peer GPU の空き VRAMから `--peer-reserve-mib`（既定600 MiB、負数は予約0 MiBとして計算）を引き、expert の層別 stride で割って配置可能な slot 数を求めます。その数に正の `--peer-slots` が指定されていれば小さい方を採用し、さらにカード0が持たない expert の数を上限にします。したがって、0 以下なら「peer GPU に収まる分」、正数なら「収まる分と指定値の小さい方」が層あたりの slot 数です。

expert の選択順は、`--expert-profile` があれば STRP v1 profile の順位を先に使い、未収録分を index 順で補います。カード0の slot と重複しないように残りの expert が選ばれ、peer に置けなかった分は CPU pool に残ります。Qwen3.6 が全 expert をカード0の VRAM に置ける場合、peer tier の初期化は行われず、peer に置く expert はありません。

peer tier の slot 用 arena は peer GPU 上に確保されます。peer 計算用の scratch・表・activation buffer 等の追加確保に失敗すると、警告を stderr に出し、peer GPU の計算 share を無効にして CPU pool が batch の全 entry を処理します。slot 数が0以下になる場合、または `cudaMemGetInfo` / slot arena の `cudaMalloc` が失敗する場合は `--peer-device` を対象とするエラーとなり、expert 配置の初期化が失敗します。

## 適用条件と副作用

- Qwen3.6 family の parser に対するオプションです。同じ文字列は通常 engine parser にもありますが、その挙動はこの文書の対象外です。
- peer GPU を使うには `--peer-device` が必要です。peer device 番号が1未満の場合、peer tier 初期化は無効で、`--peer-slots` は使われません。
- GPU メモリの照会と peer GPU 上の device memory 確保を伴います。P2P が使えない場合は peer と card 0 間の activation / rows が host 経由になると実装は説明していますが、その転送方式は `--peer-slots` 単独では切り替わりません。

## 出力とエラー

slot 配置が成功した場合、stderr に peer 上の expert 数、slot 数、予約して残した MiB 数などが記録されます。peer 用の追加 buffer が確保できない場合は peer share を無効化する警告が出ます。slot を確保できない、CUDA device を選択できない、または VRAM 情報を取得できない場合は `open_peer_tier` がエラーを返し、`place_experts` の呼び出し元はエラーを stderr に出して終了コード1を返します。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5388-5391` — Qwen3.6 parser が `--peer-slots` の値を `atoi` で読み、同じ parser で `--peer-device` を受理する。
- `engine/src/qwen35/q36_engine.cu:5466-5473` — parser の値を `Engine` に引き渡す。
- `engine/src/qwen35/q36_engine.cu:4077-4088` — peer device 未指定時の早期 return、routed expert の有無、カード0に全 expert がある場合の扱い。
- `engine/src/qwen35/q36_engine.cu:4126-4154` — 空き VRAM・reserve・slot 上限の計算、0 slot / CUDA 確保失敗時のエラー。
- `engine/src/qwen35/q36_engine.cu:4091-4109, 4188-4201` — profile 順の候補と、expert blob の peer arena へのコピー。
- `engine/src/qwen35/q36_engine.cu:4387-4396, 4540-4549` — hybrid expert 配置からの peer tier 初期化、配置結果と P2P 状態のログ。
- `engine/src/qwen35/q36_engine.cu:4203-4235` — peer 計算用 buffer 確保に失敗したときの警告と CPU pool への fallback。
- `engine/src/qwen35/q36_engine.cu:3468-3473` — peer がすでに保持する expert と card 0 側の adaptive slot 交換との重複回避。
- `engine/src/qwen35/q36_engine.cu:5522-5526` — expert 配置が失敗した場合の stderr 出力と終了コード1。
