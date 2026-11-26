# `--peer-adapt-swaps`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--peer-adapt-swaps` |
| 別名 | なし |
| 値 | 整数 `N`。0 以上は peer の適応ラウンドごとの swap 上限。負数は `--adapt-swaps` の現在値を使う |

## 役割

`--peer-device` で有効にした第2 GPU の expert cache について、適応ラウンドごとに入れ替える expert 数の上限を指定します。主 GPU 側の `--adapt-swaps` とは独立して上限を設定できます。peer を使わない場合、この値を渡しても peer の適応処理には到達しません。

## 使い方

```sh
# peer の各適応ラウンドで最大 8 件まで入れ替える
strata generate --pack /models/pack --tokens "1,2,3" \
  --expert-profile /models/profile.bin --expert-cache 256 \
  --peer-device 1 --peer-adapt-swaps 8
```

peer cache の起動には `--peer-device` に加え、expert profile と主 GPU の expert cache が必要です。上のパスと数値は利用環境に合わせてください。

## 値と既定値

- 値は parser で `std::atoi` により整数へ変換され、既定値は `-1` です。指定を省略するか負数を指定すると、適応処理へ `--adapt-swaps` の値を渡します。したがって負数は明示的な上限として使えません（`engine/src/program/generate.cpp:921,4208,15509-15510`）。
- 0 は peer の適応を行わない指定です。`PeerExperts::adapt` は `max_swaps <= 0` のとき成功扱いで直ちに戻ります（`engine/src/core/peer_experts.cpp:416-417`）。
- 明示的な範囲検証はありません。parser の値変換箇所は `engine/src/program/generate.cpp:4208` です。重複指定は引数を順に処理して同じフィールドへ代入するため、後の値が残ります（同: `3842-3847,4208`）。値の欠落は `--peer-adapt-swaps needs a value` を stderr に出し、終了コード 2 で終了します（同: `3844-3846`）。
- 値を省略したときの peer 上限は、オプションの初期値そのものではなく、適応ラウンドで参照される時点の `--adapt-swaps` 値です。`--adapt-swaps` の初期値は 96（同: `1084`）。

## 実行時の動作

peer が有効な適応ラウンドで、エンジンは使用頻度のスナップショットと主 GPU の常駐表を `PeerExperts::adapt` に渡し、上限には `N >= 0 ? N : adapt_swaps` を使います（`engine/src/program/generate.cpp:15505-15513`）。peer cache にあり主 GPU にない候補のうち、使用数が 2 以上で、peer の最少使用常駐 expert より使用数が 1.5 以上多いものを対象にします。利得の大きい順に並べた候補を上限まで選び、peer GPU の refill stream へ expert blob をコピーし、入れ替えた slot を pending として記録します（`engine/src/core/peer_experts.cpp:416-444,469-488`）。

適応の頻度はこのオプションでは変わりません。`--adapt-every` 等で決まる主適応ラウンドが走ったとき、peer も同じラウンド内で適応します。peer が未設定なら `peer.valid()` が偽となり、peer の `adapt` 呼び出しはありません（`engine/src/program/generate.cpp:15505-15513`）。

`--peer-device` が 1 以上の場合、起動時に profile と主 GPU cache の有無が確認され、満たさなければ stderr に要件を出して終了コード 1 になります（同: `10211-10222`）。

## 適用条件と副作用

- peer の cache が開かれた場合に限り有効です。`--peer-device` は第2 GPU を指定し、`--expert-profile` と正数の `--expert-cache` がない場合は起動を拒否します（`engine/src/program/generate.cpp:10211-10222`）。
- 使用頻度の条件を満たす候補がない場合や、入れ替え上限が 0 の場合は入れ替えません。候補の選定・上限適用は `engine/src/core/peer_experts.cpp:416-444` にあります。
- 選ばれた入れ替えでは、peer GPU cache の slot へ expert blob を転送し、常駐状態を更新します。コピーまたは refill event の失敗は `PeerExperts::adapt` が失敗を返し、呼び出し側が stderr に `strata serve: <エラー>` を出してラウンドを失敗扱いにします（`engine/src/core/peer_experts.cpp:469-488`、`engine/src/program/generate.cpp:15509-15513`）。
- `STRATA_EXPERT_NIBBLE` が有効な構成では、開始時の処理で `peer_adapt_swaps` 自体が 0 に上書きされ、peer 適応は停止します（`engine/src/program/generate.cpp:5485-5505`）。

## 出力とエラー

このオプション専用の成功メッセージは確認できません。値の欠落は stderr と終了コード 2、peer cache の起動条件不成立は stderr と終了コード 1 です。適応中の GPU copy/event エラーは `strata serve: <エラー>` として stderr に出て、その適応処理は失敗を返します（`engine/src/program/generate.cpp:3844-3846,10213-10222,15509-15513`、`engine/src/core/peer_experts.cpp:150-153,475-488`）。

## 根拠

- `engine/src/program/generate.cpp:916-921,1426-1432,4202-4209` — option の説明、既定値、parser 登録。
- `engine/src/program/generate.cpp:10211-10227,15505-15513` — peer cache の起動条件と値の peer 適応処理への引き渡し。
- `engine/src/core/peer_experts.hpp:71-75`、`engine/src/core/peer_experts.cpp:416-488` — peer の swap 選択、上限、コピー、失敗経路。
- `engine/sycl/src/program/generate.cpp:587-593,988,2172,9025-9033` — SYCL 側にも同じ parser 値と `adapt_swaps` への fallback がある。`docs/cli/000_cli_tools.md:10` の parser 所在一覧には SYCL 側の parser が記載されていないため、この索引範囲の記載差を補足する。索引自体は変更していない。
