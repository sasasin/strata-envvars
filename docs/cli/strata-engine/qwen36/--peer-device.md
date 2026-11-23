# `--peer-device`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 専用 parser）または `strata-q36` |
| オプション | `--peer-device` |
| 別名 | なし |
| 値 | 整数。CUDA device 番号として使用 |

## 役割

Qwen3.6 の hybrid expert 配置で、指定した CUDA device に第2の expert tier を作る。card 0 に置けなかった expert を第2 GPU に常駐させ、残りを CPU pool が処理する。decode batch のうち第2 GPU にある expert の行をそこで計算し、card 0 と CPU pool の処理に合流させる。prompt chunk はこの tier では計算せず、card 0 側の prompt 経路で処理する（`engine/src/qwen35/q36_engine.cu:3170-3199`, `3288-3314`）。

## 使い方

```sh
# Qwen3.6 の hybrid 配置で CUDA device 1 を第2 expert tier にする
strata --model /models/qwen36.gguf --peer-device 1 --tokens '1,2,3'
```

モデル指定は必須で、`strata-q36` では `--model`（別名 `--native`）として解析される。`strata` から family parser へ渡される場合も同じ Qwen3.6 parser が処理する。モデルのロードと expert 配置が成功した後、通常の生成、`--serve`、または benchmark の各経路に進む（`engine/src/qwen35/q36_engine.cu:5339-5365`, `5418-5420`, `5458-5464`, `5522-5525`, `5561-5568`）。

## 値と既定値

値は `std::atoi` で整数に変換される。値の省略時は parser の初期値 `-1`、明示的な `0` や負数も tier を無効にする。`1` 以上は第2 device を有効にする。数値形式・範囲を検証する処理はなく、たとえば非数値文字列は `atoi` により `0` として扱われる。オプションの値を省略すると `strata-q36: --peer-device needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/qwen35/q36_engine.cu:5341`, `5348-5352`, `5388`, `4077-4079`）。

## 実行時の動作

値が 1 以上でも、card 0 に全 routed experts が収まる配置では第2 tier の配置処理を行わず、「card 0 holds every expert」と stderr に出す。hybrid 配置では card 0 の slot を先に確定し、その後 `open_peer_tier` が第2 device の空き VRAMから `--peer-reserve-mib` 相当の既定 600 MiB を差し引いて slot 数を決める。`--peer-slots` が正なら上限として適用し、card 0 と同じ expert が重複配置されないようにする（`engine/src/qwen35/q36_engine.cu:5341`, `4081-4088`, `4126-4144`, `4387-4396`）。

配置順は、`--expert-profile` が指定されていれば STRP v1 profile 内の layer/expert 順を優先し、その後 profile にない expert を index 順で補う。profile は任意で、未指定時は index 順になる（`engine/src/qwen35/q36_engine.cu:4072-4076`, `4091-4109`, `4179-4192`）。

decode batch では card 0 の resident expert が優先され、第2 GPU に slot がある entry を第2 GPU で計算する。peer にない entry は CPU pool に残る。peer の stream・buffer が用意できない場合は peer share を使わず、CPU pool が全 entry を処理する（`engine/src/qwen35/q36_engine.cu:3183-3199`, `3310-3315`, `4203-4235`）。

## 適用条件と副作用

- Qwen3.6 parser は CUDA engine の `engine/src/qwen35/q36_engine.cu` にある。第2 device を CUDA runtime で選択し、その VRAM に expert arena と計算用 buffer を確保する。配置時に expert blob の host-to-device copy を行う（`engine/src/qwen35/q36_engine.cu:4077-4080`, `4120-4157`, `4193-4200`）。
- card 0 上で全 expert が収まる場合は第2 GPUに何も配置しない。hybrid 配置でないと tier の実処理は有効にならない（`engine/src/qwen35/q36_engine.cu:4330-4335`, `4387-4396`）。
- 第2 GPU の空き容量から reserve を除いた後に expert slot を1つも確保できない場合、または指定 device が存在しない場合は配置に失敗する。P2P 可否を調べ、双方で peer access がないときは activation image と結果行を host 経由で転送する旨を stderr に表示する（`engine/src/qwen35/q36_engine.cu:4120-4144`, `4547-4559`）。
- prompt chunk は peer tier で処理されず、decode 専用である。slot にない expert は CPU pool へ回る（`engine/src/qwen35/q36_engine.cu:3191-3199`, `3325-3334`）。
- device の値が `1` 以上で routed expert のないモデルを渡すと配置エラーになる（`engine/src/qwen35/q36_engine.cu:4079-4080`）。

## 出力とエラー

peer device が存在しない、VRAM 情報を取得できない、slot 用の空きがない、または expert arena の `cudaMalloc` に失敗した場合、`open_peer_tier` はエラー文字列を返す。配置呼び出し側が `strata-q36: <理由>` を stderr に出し、終了コード 1 で終了する（`engine/src/qwen35/q36_engine.cu:4121-4153`, `5522-5525`）。モデルに routed experts がない場合も同じ配置失敗経路となる（`engine/src/qwen35/q36_engine.cu:4079-4080`）。

配置に成功した hybrid 実行では、expert の card ごとの分割と P2P 状態を stderr に出す。処理終了時には peer share の entry 数、prompt chunk の扱い、tier の転送・swap 集計が条件に応じて報告される（`engine/src/qwen35/q36_engine.cu:4540-4562`, `5535-5552`）。peer 用の計算 buffer 確保だけが失敗した場合は fatal error にせず、CPU pool が batch entry を保持する旨を警告する（`engine/src/qwen35/q36_engine.cu:4203-4235`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5352`, `5388-5391`: Qwen3.6 parser の入口、値取得、既定値、関連 peer options。
- `engine/src/qwen35/q36_engine.cu:4072-4088`, `4091-4109`: tier の役割、off 条件、モデル条件、profile による配置順。
- `engine/src/qwen35/q36_engine.cu:4120-4157`, `4193-4200`: CUDA device 選択、空き容量と reserve による slot 数、確保・転送。
- `engine/src/qwen35/q36_engine.cu:3183-3199`, `3310-3334`: decode の peer share、prompt 非適用、CPU pool への fallback。
- `engine/src/qwen35/q36_engine.cu:4387-4396`, `4540-4559`, `5522-5525`: 配置の適用条件、結果表示、失敗伝播。

調査範囲は指定 revision の Strata 所有ソースに限る。GPU driver や CUDA runtime 自体の device 番号の列挙規則、P2P 性能、実機での速度・メモリ実測値は確認していない。
