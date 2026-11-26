# `--peer-reserve-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root） |
| オプション | `--peer-reserve-mib` |
| 別名 | なし（この root parser では `--peer-reserve-mib` のみ） |
| 値 | MiB 単位の整数。parser は `std::atoi` で変換する |

## 役割

`--peer-device` で指定した二枚目の GPU に専門家キャッシュを置くとき、その GPU に残す VRAM 量を指定します。値を増やすとキャッシュに割り当てる予算が減り、値を減らすとより多くの専門家を載せられます。peer tier を使わない実行ではこの値はキャッシュ割り当てに使われません。

## 使い方

```sh
strata --pack model.gguf --expert-profile profile.bin --expert-cache 1024 \
  --peer-device 1 --peer-reserve-mib 900
```

`model.gguf` と `profile.bin` は実行環境のファイルに置き換えます。peer tier には `--peer-device`、`--expert-profile`、有効な専門家キャッシュが必要です。

## 値と既定値

- 省略時は `600` MiB です。
- 値は `std::atoi` に渡されます。専用の範囲検証や不正値を拒否する分岐はありません。
- キャッシュ予算の計算時に値を最低 `128` MiB に補正します。したがって `0` や負数を指定しても、peer cache 用の空き容量を 0 MiB にする指定にはなりません。
- 同じ引数を複数回指定した場合は parser が順に代入するため、最後に現れた値が残ります。

## 実行時の動作

`--peer-device` が 1 以上の場合、エンジンは専門家プロファイルと primary 側のキャッシュをもとに peer GPU の `PeerExperts::open` を呼び出し、このオプションの値を渡します。peer GPU 上で作業用バッファ等を確保した後に空き VRAM を取得し、最低 128 MiB に補正した予約量を差し引いてキャッシュの予算を決めます。primary のキャッシュに既にある専門家は除外し、順位順に専門家を予算内へ収めます。`--peer-slots` に正数を指定している場合は、そのスロット上限にも達した時点で選定を止めます（`engine/src/program/generate.cpp:10211-10227`、`engine/src/core/peer_experts.cpp:238-284`）。

この値は peer GPU の専門家キャッシュ初期化時に使われます。prompt 用 peer バッファは別途確保され、確保できない場合には「`--peer-reserve-mib` を上げるか `--peer-prefill-rows` を下げる」旨のエラーになります（`engine/src/prefill/prefill.cpp:3501-3537`）。

## 適用条件と副作用

- `--peer-device` が 1 以上のときだけ peer tier の初期化で参照されます。peer device を指定しなければ、既定値・指定値のいずれもキャッシュ割り当てに影響しません（`engine/src/program/generate.cpp:918-920, 4205-4207, 10213-10220`）。
- `--peer-device` は `--expert-profile` と有効な専門家キャッシュを必要とします。また `--layer-split` と `--expert-cache-device1..3` は併用できません（`engine/src/program/generate.cpp:5284-5290, 10213-10217`）。
- peer GPU が無効、または primary と同じデバイスなら初期化に失敗します。peer の空き容量から予約量を引いた予算に専門家が1つも収まらない場合も失敗します（`engine/src/core/peer_experts.cpp:192-202, 264-284`）。
- 起動時に専門家キャッシュ用の GPU メモリを確保し、選ばれた専門家をロードします。初期化成功時は peer GPU 番号、常駐専門家数、容量などを標準エラーへ出力します（`engine/src/program/generate.cpp:10218-10227`）。

## 出力とエラー

- 値がない場合、parser は `<option> needs a value` を標準エラーへ出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3842-3847`）。
- `--peer-device` の前提が満たされない場合は標準エラーへ要件を出し、終了コード `1` で終了します。peer 初期化で失敗した場合も理由を標準エラーへ出して終了コード `1` になります（`engine/src/program/generate.cpp:10213-10222`）。
- peer の prompt 用バッファを確保できない場合はエラーを返します。prompt path を組み立てる箇所ではエラーを標準エラーへ出した後、prompt 処理を primary GPU に残す経路があります（`engine/src/prefill/prefill.cpp:3527-3537`、`engine/src/program/generate.cpp:13146-13153`）。

## 根拠

- `engine/src/program/generate.cpp:915-920` — peer 関連 option の既定値と説明。
- `engine/src/program/generate.cpp:1426-1433` — root CLI help 上の用途と既定値。
- `engine/src/program/generate.cpp:3842-3849, 4202-4209` — 値の取得、root parser 登録、隣接する peer options。
- `engine/src/program/generate.cpp:5284-5290, 10211-10227` — 併用制約、前提確認、予約値の受け渡し、起動結果の出力。
- `engine/src/core/peer_experts.cpp:192-202, 238-284` — device 確認、作業用バッファ確保後の空き容量計算、128 MiB 下限、キャッシュ対象の選定と容量不足時の失敗。
- `engine/src/prefill/prefill.cpp:3501-3537`、`engine/src/program/generate.cpp:13146-13153` — prompt 用バッファ不足時のエラーと primary GPU へのフォールバック。

索引では `strata-engine/root/--peer-reserve-mib.md` のほか、別 parser の `strata-engine/qwen36/--peer-reserve-mib.md` も登録されています。本書は依頼対象の root parser に限った調査です。root の根拠は `engine/src/program/generate.cpp` と `engine/src/core/peer_experts.cpp` で確認し、Qwen3.6 parser の alias `--peer-reserve` は対象外です。
