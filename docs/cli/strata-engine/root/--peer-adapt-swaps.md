# `--peer-adapt-swaps`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--peer-adapt-swaps` |
| 別名 | なし |
| 値 | 整数 `N`。peer GPU の適応キャッシュ更新で行う交換数の上限 |

## 役割

`--peer-device` で有効にした2枚目の GPU 上の expert cache について、適応更新1回で入れ替える expert 数の上限を指定します。適応更新は routing 使用数をもとに peer 上の低頻度 expert を、primary GPU と peer GPU のどちらにもない高頻度 expert で置き換えます。これは peer tier 専用の上限です。

## 使い方

```sh
strata --serve --expert-cache 4096 --expert-profile /path/to/profile.bin \
  --peer-device 1 --peer-adapt-swaps 24
```

この例では peer GPU `1` の更新1回あたりの上限を24件にします。実際に peer tier を有効にするには `--peer-device` が必要で、engine は `--expert-profile` と正の `--expert-cache` がない場合に起動を拒否します。適応ラウンドは `--serve` の decode 経路で実行されます。

## 値と既定値

- 既定値は `-1` です。値が負数なら、peer の上限には `--adapt-swaps` の値が使われます。したがって明示した `-1` は既定と同じ動作です。
- `0` 以上は peer 側の上限としてそのまま使われます。`0` なら peer の交換は行われません。
- parser は `std::atoi` で整数変換し、このオプション固有の範囲検証はありません。数値でない文字列は `atoi` の変換結果 `0` となるため、peer 更新を止める値として扱われます。複数回指定の拒否処理もなく、順に代入されるため最後の指定が残ります。
- 値を省略すると parser の `next()` が `--peer-adapt-swaps needs a value` を stderr に出して終了コード2で終了します。

## 実行時の動作

parser は `peer_adapt_swaps` の初期値を `-1` にし、指定値を `std::atoi` で格納します（`src/program/generate.cpp:570-576,2743-2747`）。適応処理では `peer_adapt_swaps >= 0` の場合はその値を、それ以外の場合は `adapt_swaps` を `PeerExperts::adapt` の `max_swaps` として渡します（`src/program/generate.cpp:10450-10458`）。

peer cache の適応候補は、usage が `2.0` 以上で primary (`res0`) と peer のどちらにも常駐していない expert です。各 layer で候補と peer 常駐 expert を usage 順に比較し、候補の usage が追い出し対象より `1.5` 以上高い場合に交換候補にします。全 layer の候補を gain 順に並べ、`max_swaps` を上限に絞ります。この peer 判定幅 `1.5` は `PeerExperts::adapt` 内で固定されており、primary cache 用の `--adapt-min-gain` とは別です（`src/core/peer_experts.cpp:335-363`; primary 側は `src/program/generate.cpp:10308-10328`）。

選ばれた expert の重みをホスト側 source から peer GPU の refill stream に非同期コピーし、コピー完了前は追い出した slot を非 resident として扱います。完了後に pending 更新を適用して新 expert を resident にします（`src/core/peer_experts.cpp:364-388`）。このオプションが直接変えるのは1回の peer 更新数であり、更新間隔は `--adapt-every`、primary の基本上限は `--adapt-swaps`、usage の減衰は `--adapt-decay` によります。

## 適用条件と副作用

- peer tier は `--peer-device N`（`N >= 1`）で初期化されます。`--expert-profile` が空、または `--expert-cache` が正でない場合、engine は stderr に要件を出し終了コード1で終了します（`src/program/generate.cpp:6750-6766`）。
- `--peer-device` は `--layer-split` および `--expert-cache-device1..3` と併用できず、該当時は stderr に理由を出して終了コード2になります（`src/program/generate.cpp:3369-3375`）。
- 更新ラウンドを実行するには adaptive tier 自体が有効である必要があります。`--adapt-every <= 0` または `--adapt-swaps <= 0` では usage 配列が作られず、peer 固有値を正にしても適応更新は起動しません（既定の `adapt_every` は4、`adapt_swaps` は96: `src/program/generate.cpp:688-698,724,16185`）。適応ラウンドの呼び出し条件は `src/program/generate.cpp:14442-14453` にあります。
- 交換数が正でも、usage 条件を満たす候補がない場合、peer に resident slot がない場合、または前回分のコピーが pending の間は交換されません（`src/core/peer_experts.cpp:335-363`）。
- 選ばれた交換では peer GPU 上の expert cache の内容と residency 表が更新されます。peer tier が有効な場合は起動時に peer 用 host buffer の portable 設定も有効化されます（`src/program/generate.cpp:2923,6750-6766`）。この option 自体はファイル出力やネットワーク接続を行いません。
- `--adapt-async 1` は peer GPU と併用できず、engine は非同期適応を無効にして blocking tier を使います（`src/program/generate.cpp:8077-8092`）。

## 出力とエラー

parser の数値変換後にこの値だけを理由とする validation error はありません。未知のオプションは `unknown argument` と usage を stderr に出し終了コード2、値を欠いた場合も終了コード2です（`src/program/generate.cpp:2417-2423,2787-2793`）。

peer 更新中に refill copy または event 登録が失敗すると `PeerExperts::adapt` が失敗を返し、呼び出し側が `strata serve: <エラー>` を stderr に出して適応処理を失敗として伝播します（`src/core/peer_experts.cpp:364-377`; `src/program/generate.cpp:10450-10458`）。

## 根拠

- parser と既定値: `src/program/generate.cpp:570-576,2743-2747`
- peer の起動要件と初期化: `src/program/generate.cpp:3369-3375,6750-6766`
- 値の選択と peer 更新の呼び出し: `src/program/generate.cpp:10450-10458`
- peer 候補選択、上限適用、GPU copy、pending の適用: `include/strata/core/peer_experts.hpp:70-74`; `src/core/peer_experts.cpp:335-388`
- 適応 cadence と primary 側上限の有効条件: `src/program/generate.cpp:688-698,724,14442-14453,16185`
- 索引上のスコープと予定リンク: `docs/cli/README.md:1128-1134,1243-1247`

調査範囲は上記 commit の checkout にある native engine parser と peer cache 実装です。CLI バイナリの `--help` は実行しておらず、Release 配布物や GPU 実機での実動作は確認していません。
