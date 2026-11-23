# `--expert-profile`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 family parser。独立入口 `strata-q36` も同じ parser） |
| オプション | `--expert-profile` |
| 別名 | なし |
| 値 | STRP v1 profile ファイルのパス |

## 役割

`--peer-device` で有効にする2枚目の CUDA GPU の expert tier に、どの expert を優先して載せるかを指定する。Qwen3.6 のこの parser では、1枚目の GPU の配置や通常の expert cache 順序を直接変える指定ではない。

## 使い方

```sh
strata --model /models/qwen36.gguf --peer-device 1 --expert-profile /data/qwen36.strp --serve
```

この例は Qwen3.6 model をロードし、ハイブリッド配置で2枚目の CUDA device 1 に空き VRAM があるとき、profile 順を peer tier の配置に使う。profile は `--dump-expert-profile` で生成したファイルなど、対象モデルに合う STRP v1 を指定する。

## 値と既定値

- 値は次の argv 要素から受け取るパス文字列。値を省略すると parser は `strata-q36: --expert-profile needs a value` を stderr に出して終了コード 2 で終了する。複数回指定した場合は parser が読むたびに同じ変数へ代入するため、最後の値が残る（`engine/src/qwen35/q36_engine.cu:5350-5352, 5391`）。
- 既定値は空文字列（profile なし）。空文字列を指定した場合も profile 読み込みを行わず、peer tier は card 0 の先頭 expert を除いて expert index 順に候補を作る（`engine/src/qwen35/q36_engine.cu:5340-5341, 4091-4092, 4179-4192`）。
- peer loader はファイル先頭の `STRP` magic と version 1 を検査する。header の layer 数・expert 数・slot 数はモデルや配置と照合しない。header の ranked pair 数ぶんを読み、途中で読み取りが途切れるとそこで打ち切る。範囲外 pair は読み込んだ pair 数に含めず破棄し、有効 pair 数を stderr に出す。重複 pair も後段で一度だけ採用される（`engine/src/qwen35/q36_engine.cu:4093-4109, 4182-4192`）。

## 実行時の動作

parser は値を `expert_profile` に保存し、`Engine` に渡す（`engine/src/qwen35/q36_engine.cu:5391, 5466-5474`）。expert 配置がハイブリッドになり、かつ `--peer-device` が有効なとき、`open_peer_tier()` が profile を読み、層ごとの ranked pair を `want` に追加する。そこから card 0 が保持する expert と重複しない pair を先に並べ、不足分は expert index 順で補う。peer tier の slot 数に達したところまでの順序で実際に GPU へ配置する（`engine/src/qwen35/q36_engine.cu:4084-4109, 4179-4195`）。

## 適用条件と副作用

- profile を読むのは `--peer-device` の値が 1 以上で、expert が1枚目の GPU に全て収まらず、ハイブリッド配置の計画が成立した場合に限る。peer device 無効なら loader は直ちに戻り、全 expert が1枚目に収まる場合は配置処理自体が早期 return するため、どちらも profile は開かれない（`engine/src/qwen35/q36_engine.cu:4077-4078, 4318-4335, 4380-4392`）。
- hybrid 配置でも CPU expert pool を含まない build では peer loader に進む前に配置失敗となる（`engine/src/qwen35/q36_engine.cu:4337-4341`）。
- `--peer-device` と組み合わせる指定であり、card 0 の slot 数は peer 配置の先頭除外範囲を決める。MTP-only または `STRATA_Q36_PEER_VS_C0` 検証経路では除外範囲を 0 として peer tier が profile 順を使う（`engine/src/qwen35/q36_engine.cu:4387-4392`）。
- profile は読み取り専用で開く。指定ファイル自体の変更はない。peer tier のための CUDA device 選択・メモリ確保は `--peer-device` による処理で、profile の存在だけでは起動しない（`engine/src/qwen35/q36_engine.cu:4077-4078, 4120-4156`）。

## 出力とエラー

- profile を使った場合、読み込んだ有効 pair 数と header の pair 数を stderr に表示する（`engine/src/qwen35/q36_engine.cu:4108-4109`）。
- ファイルを開けない場合は `--expert-profile <path>: cannot open`、`STRP` magic 不一致または version 不一致の場合は `--expert-profile <path>: not an STRP v1 profile` が配置エラーとして報告され、呼び出し元は stderr に `strata-q36: ...` を出して終了コード 1 を返す（`engine/src/qwen35/q36_engine.cu:4093-4100, 5522-5526`）。
- loader は header の layer/expert dimensions を検査せず、範囲外 pair は無視する。また ranked pair 部分の EOF/短い読み取りはエラーではなく読み込み打ち切りになる。したがって、ファイルが対象モデル用かどうかを parser が完全検証するとは確認できない（`engine/src/qwen35/q36_engine.cu:4097-4109, 4182-4192`）。
- peer tier の GPU 確保や空き slot が失敗した場合も配置エラーになり、呼び出し元が終了コード 1 を返す。これらは `--peer-device` の allocation 条件に関する失敗である（`engine/src/qwen35/q36_engine.cu:4121-4154, 5522-5526`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5392` — Qwen3.6 parser、必須値取得、値の保存。索引はこの parser scope を `strata-engine/qwen36/` としている（`docs/cli/README.md:1240-1255`）。
- `engine/src/qwen35/q36_engine.cu:4077-4109, 4179-4195` — peer tier の適用条件、STRP v1 読み込み、rank 順の採用と index 順 fallback。
- `engine/src/qwen35/q36_engine.cu:3411-3442` — 同じ parser の `--dump-expert-profile` が routing count を STRP v1 形式で出力する処理。
- `engine/src/qwen35/q36_engine.cu:4318-4392, 5522-5526` — 全 expert が VRAM に収まる早期終了、hybrid 配置、peer loader 呼び出し、配置エラーの終了経路。
- `docs/cli/001_investigation.md:56-74, 76-119` — 調査対象・配置・オプション文書の基準。
