# `--adapt-swaps`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数 parser） |
| オプション | `--adapt-swaps` |
| 別名 | なし |
| 値 | 整数 `N`。1回の expert cache 適応で選ぶ交換数の上限 |

## 役割

ルーティング状況に応じて GPU の expert cache の常駐内容を入れ替える適応 tier について、1回の適応で選ぶ交換数を制限します。値を正にするだけでは適応 tier は始まりません。`--adapt-every` も正であること、GPU cache に未常駐 expert があることが必要です。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --adapt-swaps 32
```

この例は `src/program/generate.cpp` に記載された engine parser の `--pack` / `--tokens` 構文に基づきます。実際に使うモデルや pack に合わせて入力を指定してください。

## 値と既定値

- 既定値は `96` です。
- parser は次の引数を `std::atoi` で整数に変換し、`adapt_swaps` に設定します。明示的な範囲検証や上限補正はこの parser 分岐にはありません。数値として読めない値は `atoi` により `0` となり、適応を止める値として扱われます。
- `0` 以下では適応用の routing usage 配列を作らず、適応 tier はオフになります。したがって負数もこの条件では無効化として働きます。
- 同じオプションを複数回指定した場合、引数を順に読み込んで同じフィールドへ代入するため、後の指定が残ります。
- 値を省略すると `--adapt-swaps needs a value` を stderr に出し、parser は終了コード `2` で終了します。

## 実行時の動作

適応用の usage 配列は、`--adapt-every > 0` かつ `--adapt-swaps > 0` の場合にだけ確保されます。全 expert がすでに GPU 上にある場合も確保されず、適応処理は走りません。したがって、この値は交換数を指定するだけで、cache の構築や常駐可能数を直接決めるものではありません。

適応間隔ごとに各 layer の routing usage を見て、未常駐のうち usage が `2.0` 以上の expert を候補にし、常駐中の usage が少ない expert と比較します。serve の通常経路では差が `--adapt-min-gain` を超えた候補を採用します。全 layer の候補を優先度順に並べた後、primary cache ではこのオプションの値を超える分を切り捨てます。別の speculative decode 経路では同じ差の閾値 `1.5` がコードに固定されています。選ばれた expert のデータを cache にコピーし、追い出された expert は CPU 側の source に戻します。routing usage は適応後に `--adapt-decay` 倍されます。

適応は decode の window / round の進行に沿って行われます。間隔には `--adapt-every` が使われ、内部の warm-up interval が有効な経路では一時的にそちらが使われます。`--adapt-async` や `--pipeline-windows` が有効な経路では、適応の選択・コピーが推論 window と並行または非同期で進む場合があります。

値の上限は経路で異なります。resident RAM の通常経路では交換 buffer の確保数が `min(N, 96)` に制限され、arena 経路では内部 cap が `N` です。したがって 96 を超える値が毎回その数の交換を実行する保証はなく、実際の候補数や経路の制約も受けます。

`--peer-device` を使う場合、この値は primary cache の交換上限に加えて、peer 側の `--peer-adapt-swaps` の既定値にもなります。peer 用の値が明示されていれば、そちらが peer の交換上限を決めます。remote expert optimization の適応処理にも同じ値が別途渡されます。

## 適用条件と副作用

- `--adapt-every` が `0` 以下、`--adapt-swaps` が `0` 以下、または全 expert が GPU cache に常駐している場合、適応 tier は動きません。
- 適応対象は、未常駐で routing usage が閾値を満たし、peer / remote tier や helper に保持されていない expert です。常駐 expert の中から利用回数が低いものを選んで入れ替え先にします。
- resident RAM mode では、正の適応設定に応じて交換 buffer を確保します。初期化時の説明出力は、このモードの適応交換を「GPU cache と交換（ファイル読み込みなし）」として示します。
- 交換時には expert データの host-to-device copy が発生し、追い出した expert は非常駐扱いになって source から再利用できるようにされます。実際に選ばれる数やタイミングは routing と実行経路に依存します。

## 出力とエラー

- 起動時に parser 独自の値範囲エラーはありません。値を省略した場合は前述の stderr メッセージと終了コード `2` になります。
- resident RAM mode の初期化で交換 buffer を確保できない場合、理由を stderr に出して engine は終了コード `1` で抜けます。
- 実行中の adaptive refill / copy に失敗すると、serve 経路では `strata serve: adaptive swap copy failed...` 等を stderr に出し、適応失敗として処理します。decode 経路でも `ERR an adaptive refill failed` などを出して終了コード `1` となる経路があります。
- このオプション単独では専用の出力を行いません。適応が無効な場合の理由表示は、serve の他設定や実行モードによって異なります。

## 根拠

- `src/program/generate.cpp:688-702,724` — 適応間隔・decay・async の既定値と `adapt_swaps = 96`。
- `src/program/generate.cpp:2416-2421,2740` — parser の値取得と `std::atoi` による代入。欠落値は parser 共通処理で終了コード `2`。
- `src/program/generate.cpp:2787-2793` — 未知引数の stderr、usage 表示、終了コード `2`。
- `src/program/generate.cpp:8250-8270` — resident RAM mode の交換 buffer 確保、確保失敗、適応の on/off 表示。
- `src/program/generate.cpp:10028-10029,16185-16197` — 正の適応設定と未常駐 expert がある場合の usage 配列確保、および適応関連状態。
- `src/program/generate.cpp:10302-10328,10336-10435,10446-10460` — serve 経路の候補選定、交換上限、コピー・失敗処理、peer / decay との関係。
- `src/program/generate.cpp:10450-10458` — `--peer-adapt-swaps` が未指定なら `--adapt-swaps` を peer の上限に使う処理。
- `src/program/generate.cpp:10530-10545` — arena と通常経路の非同期交換 cap。
- `src/program/generate.cpp:14442-14453,15119-15133,16662-16675` — 適応の cadence と非同期実行、decode 時の失敗報告。
- `src/program/generate.cpp:16281-16325,16341-16379` — 別の speculative decode 経路での適応選定、交換上限、copy と usage decay。

## 調査範囲

調査対象は上記 commit の checkout 内の parser と実装です。調査時に Release artifact やビルド済み CLI の help は照合していません。また、build・GPU 実行・性能測定は行っていないため、backend や機器ごとの実測効果は記載していません。
